import streamlit as st
import sqlite3
import cv2
import face_recognition
import os
import random

# Ensure the 'faces' directory exists
os.makedirs('faces', exist_ok=True)

# Database Connection
def get_db_connection():
    conn = sqlite3.connect('users.db')
    return conn

# Create Database Table
def create_table():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    account_number TEXT PRIMARY KEY,
                    user_name TEXT NOT NULL,
                    pin TEXT NOT NULL,
                    contact_number TEXT NOT NULL,
                    balance REAL DEFAULT 0.0)''')
    conn.commit()

# Register User
# Register User
def register_user():
    st.subheader("Register a New User")
    account_number = st.text_input("Account Number")
    user_name = st.text_input("User Name")
    pin = st.text_input("PIN", type="password")
    contact = st.text_input("Phone Number")
    initial_balance = st.number_input("Initial Deposit Amount", min_value=0.0, format="%.2f")

    if st.button("Register"):
        if account_number == "" or pin == "" or contact == "" or user_name == "":
            st.warning("All fields must be filled!")
            return

        conn = get_db_connection()
        c = conn.cursor()

        # Check if account number already exists
        c.execute("SELECT * FROM users WHERE account_number = ?", (account_number,))
        if c.fetchone():
            st.warning("Account number already exists!")
            return

        # Save user data to the database
        c.execute("INSERT INTO users (account_number, user_name, pin, contact_number, balance) VALUES (?, ?, ?, ?, ?)",
                  (account_number, user_name, pin, contact, initial_balance))
        conn.commit()

        # Capture and save the user's face
        st.info("Please look at the camera to capture your face.")

        video = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Use DirectShow backend for Windows
        face_captured = False

        for _ in range(20):  # Try capturing multiple frames
            status, frame = video.read()
            if not status:
                st.error("Unable to access the camera. Please check your setup.")
                video.release()
                return
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            st.image(frame_rgb, caption="Camera Feed", channels="RGB")
            face_locations = face_recognition.face_locations(frame_rgb)

            if face_locations:  # If a face is detected
                # Save the face image
                face_captured = True
                face_path = os.path.join('faces', f"{account_number}.jpg")
                cv2.imwrite(face_path, frame)
                st.success("Face captured and saved successfully!")
                break

        video.release()

        if not face_captured:
            st.warning("No face detected. Please try registering again.")
            # Rollback database changes if face is not captured
            c.execute("DELETE FROM users WHERE account_number = ?", (account_number,))
            conn.commit()
            return

        st.success("User Registered Successfully!")


# Login Page
def login_user_screen():
    st.subheader("User Login")
    account_number = st.text_input("Account Number")
    pin = st.text_input("PIN", type="password")

    if st.button("Login"):
        if account_number == "" or pin == "":
            st.warning("Please enter both account number and PIN!")
            return

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE account_number = ? AND pin = ?", (account_number, pin))
        user = c.fetchone()

        if user is None:
            st.warning("Invalid account number or PIN!")
            return

        # Verify Face
        st.info("Verifying face. Please look at the camera.")
        video = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Use DirectShow backend for Windows
        face_encoding = None

        for _ in range(10):  # Try capturing multiple frames
            status, frame = video.read()
            if not status:
                st.error("Unable to access the camera. Please check your setup.")
                video.release()
                return
            
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            st.image(frame_rgb, caption="Camera Feed", channels="RGB")
            face_encoding = face_recognition.face_encodings(frame_rgb)

            if face_encoding:
                face_encoding = face_encoding[0]
                break

        video.release()

        if face_encoding is None:
            st.warning("No face detected during login!")
            return

        # Load saved face image and compare
        saved_image_path = os.path.join('faces', f"{account_number}.jpg")
        if not os.path.exists(saved_image_path):
            st.error("No face image found for this account. Contact support.")
            return

        saved_image = face_recognition.load_image_file(saved_image_path)
        saved_face_encoding = face_recognition.face_encodings(saved_image)[0]

        matches = face_recognition.compare_faces([saved_face_encoding], face_encoding)

        if matches[0]:
            st.success("Face Verified Successfully!")
            st.session_state.logged_in_user = user
            st.session_state.generated_otp = str(random.randint(1000, 9999))  # Generate OTP
            st.session_state.screen = "otp_verification"  # Transition to OTP verification page
        else:
            st.error("Face does not match! Emergency alert triggered.")
            st.warning(f"Alert sent to registered phone number: {user[3]}")

# OTP Verification Page
def otp_verification_screen():
    st.subheader("OTP Verification")
    if "generated_otp" not in st.session_state:
        st.warning("Please log in first to generate an OTP.")
        return

    otp = st.session_state.generated_otp  # Retrieve generated OTP from session state
    st.info(f"Your OTP is: {otp} (For demonstration purposes, it's displayed here)")
    user_otp = st.text_input("Enter OTP", type="password")

    if st.button("Verify OTP"):
        if user_otp == otp:
            st.success("OTP Verified Successfully!")
            st.session_state.screen = "post_login"  # Set next screen
        else:
            st.error("Invalid OTP! Try again.")
    
    # Back Button
    if st.button("Back to Login"):
        st.session_state.screen = "main"  # Go back to login page

# Check Balance, Withdraw, and Transfer
def balance_screen():
    st.subheader("Account Balance Options")

    # Get user from session state
    user = st.session_state.logged_in_user
    conn = get_db_connection()
    c = conn.cursor()

    # Use columns for neat layout
    col1, col2, col3 = st.columns(3)

    # Option to Check Balance
    with col1:
        if st.button("Check Balance", key="check_balance", use_container_width=True):
            c.execute("SELECT balance FROM users WHERE account_number = ?", (user[0],))
            balance = c.fetchone()[0]
            st.info(f"Your current balance is: ₹{balance:.2f}")

    # Option to Withdraw Balance
    with col2:
        if st.button("Withdraw Balance", key="withdraw_balance", use_container_width=True):
            amount = st.number_input("Enter withdrawal amount", min_value=0.0, format="%.2f")
            c.execute("SELECT balance FROM users WHERE account_number = ?", (user[0],))
            current_balance = c.fetchone()[0]
            if amount > current_balance:
                st.warning("Insufficient Balance!")
            else:
                new_balance = current_balance - amount
                c.execute("UPDATE users SET balance = ? WHERE account_number = ?", (new_balance, user[0]))
                conn.commit()
                st.success(f"₹{amount:.2f} withdrawn successfully! New balance: ₹{new_balance:.2f}")

    # Option to Transfer Balance
    with col3:
        if st.button("Transfer Balance", key="transfer_balance", use_container_width=True):
            target_account = st.text_input("Enter Target Account Number")
            amount = st.number_input("Enter transfer amount", min_value=0.0, format="%.2f")

            # Check if target account exists
            c.execute("SELECT balance FROM users WHERE account_number = ?", (target_account,))
            target = c.fetchone()

            if target is None:
                st.warning("Target account does not exist!")
            else:
                c.execute("SELECT balance FROM users WHERE account_number = ?", (user[0],))
                current_balance = c.fetchone()[0]
                if amount > current_balance:
                    st.warning("Insufficient Balance!")
                else:
                    new_balance = current_balance - amount
                    target_new_balance = target[0] + amount
                    c.execute("UPDATE users SET balance = ? WHERE account_number = ?", (new_balance, user[0]))
                    c.execute("UPDATE users SET balance = ? WHERE account_number = ?", (target_new_balance, target_account))
                    conn.commit()
                    st.success(f"₹{amount:.2f} transferred successfully to account {target_account}!")

    # Back Button
    if st.button("Back to Login"):
        st.session_state.screen = "main"  # Go back to login page

# Main Navigation Logic
def main():
    st.title("e-ATM System with Face and OTP Authentication")

    # Initialize session state
    if "screen" not in st.session_state:
        st.session_state.screen = "main"

    # Render the appropriate screen based on session state
    if st.session_state.screen == "main":
        menu = ["Register", "Login", "OTP Verification", "Check Balance"]
        choice = st.sidebar.selectbox("Menu", menu)
        create_table()  # Initialize Database

        if choice == "Register":
            register_user()
        elif choice == "Login":
            login_user_screen()
        elif choice == "OTP Verification":
            otp_verification_screen()
        elif choice == "Check Balance":
            if "logged_in_user" in st.session_state:
                balance_screen()
            else:
                st.warning("You must log in first!")

    elif st.session_state.screen == "otp_verification":
        otp_verification_screen()

    elif st.session_state.screen == "post_login":
        balance_screen()

if __name__ == "__main__":
    main()