

import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import pytz
#change1
from fpdf import FPDF
import qrcode
import io
import os
mongo_url = st.secrets["url"]
client = MongoClient(mongo_url)
db = client["visitor_app_db"]
users_collection = db["users"]
requests_collection = db["visitor_requests"]



def check_login(username, password):
    user = users_collection.find_one({"username": username, "password": password})
    if user: return user["role"]
    return None

def insert_request(user, visitor_name, contact, visit_date, purpose):
    ist = pytz.timezone('Asia/Kolkata')
    requests_collection.insert_one({
        "requested_by": user,
        "visitor_name": visitor_name,
        "contact": contact,
        "visit_date": str(visit_date),
        "purpose": purpose,
        "status": "Pending",
        "admin_comment": "",
        "timestamp": datetime.now(ist).strftime("%Y-%m-%d %H:%M"),
    })

def get_user_requests(user):
    return list(requests_collection.find({"requested_by": user}, {'_id': 0}))

def get_all_requests():
    return list(requests_collection.find({}))

def update_request_status(request_id, status, comment):
    requests_collection.update_one(
        {"_id": request_id}, {"$set": {"status": status, "admin_comment": comment}})
    #Change

def generate_pdf_for_request(request, logo_path="logo.png"):
    pdf = FPDF()
    pdf.add_page()
    
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=10, y=8, w=30)
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 20, 'Visitor Pass', ln=True, align='C')
    pdf.ln(10)


    pdf.set_font('Arial', '', 12)
    fields = [
        ("Request ID", str(request.get('_id', ''))),
        ("Requested By", request['requested_by']),
        ("Visitor Name", request['visitor_name']),
        ("Contact", request['contact']),
        ("Visit Date", request['visit_date']),
        ("Purpose", request['purpose']),
        ("Status", request['status']),
        ("Admin Comment", request.get('admin_comment', '')),
        ("Timestamp", request['timestamp']),
    ]
    for label, val in fields:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(45, 10, f"{label}:", 0, 0)
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, val, ln=True)


    qr_content = f"""Request ID: {str(request.get('_id',''))}
Visitor Name: {request.get('visitor_name','')}
Date: {request.get('visit_date','')}
Status: {request.get('status','')}"""
    qr_img = qrcode.make(qr_content)
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf)
    qr_buf.seek(0)
    qr_file = "qr_temp.png"
    with open(qr_file, "wb") as f:
        f.write(qr_buf.read())
    y_pos = pdf.get_y() + 10
    pdf.image(qr_file, x=150, y=y_pos, w=40)
    if os.path.exists(qr_file): os.remove(qr_file)

    
    pdf_bytes = pdf.output(dest='S').encode('latin1')  
    pdf_buf = io.BytesIO(pdf_bytes)
    return pdf_buf





def login_section():
    st.sidebar.title("Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type='password')
    if st.sidebar.button("Login"):
        role = check_login(username, password)
        if role:
            st.session_state["user"] = username
            st.session_state["role"] = role
            #change3
            st.session_state.pop("just_approved_request_id", None)
            st.session_state.pop("pdf_ready", None) #tillhere
            st.rerun()
        else:
            st.sidebar.error("Incorrect username or password.")

def user_section(user):
    st.header("Request a Visitor Pass")
    with st.form("request_form"):
        visitor_name = st.text_input("Visitor Name")
        contact = st.text_input("Contact Number")
        visit_date = st.date_input("Date of Visit")
        purpose = st.text_area("Purpose of Visit")
        submitted = st.form_submit_button("Submit Request")
        if submitted:
            insert_request(user, visitor_name, contact, visit_date, purpose)
            st.success("Request submitted!")

    st.header("My Requests")
    my_reqs = get_user_requests(user)
    if my_reqs:
        st.table(my_reqs)
    else:
        st.info("No requests found.")

def admin_section():
    st.header("All Visitor Pass Requests")
    all_reqs = get_all_requests()
    for req in all_reqs:
        req_id = req['_id']
        st.markdown(f"**Date:** {req['timestamp']} • **Requestor:** {req['requested_by']} • **Visitor:** {req['visitor_name']} • **Status:** {req['status']}")
        if req['status'] == "Pending":
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"Approve", key=f"approve_{req_id}"): #change
                    update_request_status(req_id, "Approved", "Approved")
                    st.session_state["just_approved_request_id"] = req_id #change
                    st.rerun()
            with col2:
                if st.button(f"Reject", key=f"reject_{req_id}"): #change
                    update_request_status(req_id, "Rejected", "Rejected")
                    st.rerun()
        #change            
        if st.session_state.get("just_approved_request_id") == req_id and req['status'] == "Approved":
            pdf_buf = generate_pdf_for_request(req)
            st.download_button(
                label="Download Visitor Pass PDF",
                data=pdf_buf,
                file_name=f"VisitorPass_{req_id}.pdf",
                mime="application/pdf",
                key=f"download_{req_id}"
            )
      
    st.header("All Requests Table")
    if all_reqs:
        display_reqs = [{k: v for k, v in req.items() if k != '_id'} for req in all_reqs]
        st.table(display_reqs)
    else:
        st.info("No requests found.")




def main():
    st.title("NALCO CISF Visitor Pass System ")
    if "user" not in st.session_state:
        login_section()
        st.stop()
    user = st.session_state["user"]
    role = st.session_state["role"]
    if role == "user":
        user_section(user)
    elif role == "admin":
        admin_section()
    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())

if __name__ == "__main__":
    main()
