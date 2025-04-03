from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import openai
from datetime import datetime
import json
import os
import sqlite3
from history_samba_continuous_function import generate_response as llm_generate_response
import csv
import razorpay
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from email.mime.base import MIMEBase
from email import encoders
import tempfile
import qrcode
from PIL import Image
import pandas as pd
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'simple_chatbot_secret_key'

# Global initial conversation history
from datetime import datetime

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=("rzp_test_MnUkBLUn8EYdag", "T4B2r4yhjBEfOlbVwVZ5qUW6"))

# Ticket prices (in rupees)
CHILD_TICKET_PRICE = 25
ADULT_TICKET_PRICE = 50

# Email Configuration
EMAIL_ADDRESS = "meheraablook@gmail.com"
EMAIL_PASSWORD = "ouyd wxxu rmhw ygua"  # App Password

# Add new system prompt for unavailable slots
UNAVAILABLE_SLOT_PROMPT = {
    "role": "system",
    "content": """
The selected date and time are unavailable. Inform the user that their chosen slot is not available and ask them to select a different date and time.

### Response format:
{
  "response": "<Inform the user that the selected slot is unavailable and ask them to choose another date and time>",
  "entities": {
    "date": null,
    "time": null
  }
}
"""
}

def get_current_date():
    """Returns the current date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")

# Get today's date to supply to the chatbot
current_date = get_current_date()

INITIAL_CONVERSATION_HISTORY = [{
    "role": "system",
    "content": f"""
You are an AI-powered chatbot for an online museum ticketing system.

Your tasks:
1. Booking tickets
2. Updating existing bookings
3. Deleting bookings
4. Engaging in general conversation

### IMPORTANT RULES:
1. **Always identify the user's intent first** before generating a response.
2. **Always return responses in a valid JSON format**. No exceptions.
3. **Never miss asking for missing information**. If any field is `null`, prompt the user to provide it.

### RESTRICTIONS:
- Do **not** mention reference numbers.
- Do **not** provide ticket prices or costs in responses.
- Do **not** tell the user that their details have been sent via phone or email.

### FAQs:
- **Ticket Prices**:
  - Adult (18+): 50
  - Child (Under 18): 25
- **Museum Timings**:
  - Open from **10:00 AM to 6:00 PM**.
  - **Closed on Mondays**.

### Response format:
#### For booking a ticket:
{{
  "response": "<Reply to the user>",
  "task": "<One of: 'booking_ticket', 'updating_booking', 'deleting_booking', 'general_chat'>",
  "entities": {{
    "name": "<Extracted name or null>",
    "phone_number": "<Extracted phone number or null>",
    "email": "<Extracted email address or null>",
    "children_tickets": "<Number of child tickets (under 18) or null>",
    "adult_tickets": "<Number of adult tickets (18+) or null>",
    "date": "<Extracted date in YYYY-MM-DD format or null>",
    "time": "<Extracted time in HH:MM format or null>"
  }}
}}

#### For updating a ticket:
{{
  "response": "<Reply to the user>",
  "task": "<One of: 'booking_ticket', 'updating_booking', 'deleting_booking', 'general_chat'>",
  "entities": {{
    "phone_number": "<Extracted phone number or null>",
    "date": "<Extracted date in YYYY-MM-DD format or null>",
    "time": "<Extracted time in HH:MM format or null>"
  }}
}}

#### For deleting a ticket:
{{
  "response": "<Reply to the user>",
  "task": "<One of: 'booking_ticket', 'updating_booking', 'deleting_booking', 'general_chat'>",
  "entities": {{
    "phone_number": "<Extracted phone number or null>"
  }}
}}

### Rules for Processing:
1. **Intent Classification**: Identify the user's request and classify it as one of the four tasks.
2. **Entity Extraction**: Extract the required details based on the identified intent.
3. **Ticket Categorization**:
   - Always separate tickets into `children_tickets` (under 18) and `adult_tickets` (18+).
   - If the user gives a total number of tickets without specifying, ask how many are for children and how many are for adults.
4. **Date Handling**:
   - Use `YYYY-MM-DD` format.
   - Today's date is `{current_date}`.
   - If the user provides a weekday (e.g., "Saturday"), return the next occurrence of that day relative to `{current_date}`.
   - If the user says "tomorrow," return `{current_date} + 1 day`.
   - **Do not allow bookings for Mondays.** If the user selects a Monday, inform them and ask for another date.
5. **Time Handling**:
   - Convert times into `HH:MM` (24-hour format).
   - Examples: "3 AM" → "03:00", "2 PM" → "14:00", "07:45 PM" → "19:45".
   - **Only allow bookings between 10:00 and 18:00 (6 PM).** If the user selects an invalid time, inform them and ask for a valid time.
6. **Updating a Booking**:
   - If the intent is `updating_booking`, ask the user for their `phone_number`.
   - Also, request `date` and `time` for the updated booking.
   - If `date` and `time` are missing, set them as `null` and prompt the user to provide them.
7. **Deleting a Booking**:
   - If the intent is `deleting_booking`, only ask for the `phone_number`.
   - No need to collect additional details for deletion.
8. **Missing Fields**:
   - If any required entity is `null`, always prompt the user to provide it.
"""
}]





class ChatState:
    def __init__(self):
        self.conversation_history = INITIAL_CONVERSATION_HISTORY.copy()
        self.conversation_title = None
        self.filename = None
        self.payment_completed = False
        self.selected_booking_id = None  # Track selected booking

# Store chat states for different users
chat_states = {}

def get_chat_state():
    """Get or create chat state for current session"""
    user_id = session.get('user_id')
    if user_id not in chat_states:
        chat_states[user_id] = ChatState()
    return chat_states[user_id]

def validate_login(username, password):
    """Validate login credentials against the database"""
    db_path = r'E:\major project\project files\simple_chatbot\users.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check credentials against database
    cursor.execute('SELECT id FROM users WHERE username = ? AND password = ?', 
                  (username, password))
    result = cursor.fetchone()
    
    conn.close()
    return result[0] if result else None

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('chat'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_id = validate_login(username, password)
        if user_id:
            session['user_id'] = user_id  # Store the numeric user ID
            return redirect(url_for('chat'))
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html', initial_message="Welcome to Smart Museum! I can help you book tickets, update bookings, or answer any questions about our exhibits. How may I assist you today?")

def command_checker(user_message: str, conversation_history: list) -> str:
    """Check if the message is a command and handle it"""
    if user_message.strip().lower() == "/print":
        print("________________________________________________________________")
        print("Conversation History:")
        for msg in conversation_history:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            print(f"{role}: {content}")
        print("________________________________________________________________")
        return "Command executed: Conversation history printed to terminal"
    return None

def check_slot_availability(date, time, total_tickets):
    """Check if the selected slot has enough capacity"""
    try:
        # Read the slots CSV
        slots_df = pd.read_csv('simple_chatbot/museum_ticket_slots.csv')
        
        # Find the matching slot
        slot = slots_df[(slots_df['date'] == date) & (slots_df['time'] == time)]
        
        if slot.empty:
            return False
        
        # Check if enough slots are available
        available_slots = slot['slots'].iloc[0]
        return available_slots >= total_tickets
        
    except Exception as e:
        print(f"Error checking slot availability: {e}")
        return False

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    state = get_chat_state()
    user_message = request.json.get('message')
    
    # Check for commands
    command_response = command_checker(user_message, state.conversation_history)
    if command_response:
        return jsonify({
            'response': command_response,
            'update_sidebar': False
        })
    
    # If this is the first message, set it as the conversation title
    should_update_sidebar = False
    if not state.conversation_title or not state.filename:
        state.conversation_title = user_message
        state.filename = initialize_new_conversation(user_message)
        should_update_sidebar = True
    
    # Use the imported generate_response function
    response, state.conversation_history = llm_generate_response(
        user_message, 
        state.conversation_history
    )
    
    # Log the response to terminal if it's valid JSON
    try:
        parsed_json = json.loads(response)
        print("\n=== LLM JSON Response ===")
        print(json.dumps(parsed_json, indent=2))
        print("========================\n")
    except json.JSONDecodeError:
        # Not valid JSON, no need to log
        pass
    
    # Update conversation file
    if state.filename:
        update_conversation_file(state.conversation_title, state.conversation_history, state.filename)
    
    # Parse the response to check for task type
    try:
        parsed_response = json.loads(response)
        display_response = parsed_response.get('response', response)
        task = parsed_response.get('task', 'general_chat')
        entities = parsed_response.get('entities', {})
        
        # Handle updating booking
        if task == 'updating_booking' and entities.get('phone_number'):
            phone_number = entities.get('phone_number')
            bookings = get_bookings_by_phone(phone_number)
            
            if bookings:
                # If a booking is already selected, don't show options again
                if state.selected_booking_id:
                    booking = next((b for b in bookings if b['booking_id'] == state.selected_booking_id), None)
                    if booking:
                        # If date and time are provided, confirm update for selected booking
                        if entities.get('date') and entities.get('time'):
                            return jsonify({
                                'response': display_response,
                                'update_sidebar': should_update_sidebar,
                                'show_update_confirmation': True,
                                'booking': booking,
                                'new_date': entities.get('date'),
                                'new_time': entities.get('time')
                            })
                        else:
                            return jsonify({
                                'response': f"I have your booking for {booking['date']} at {booking['time']}. What date and time would you like to change it to?",
                                'update_sidebar': should_update_sidebar
                            })
                # No booking selected yet, show options
                # If date and time are provided, confirm update
                elif entities.get('date') and entities.get('time'):
                    return jsonify({
                        'response': display_response,
                        'update_sidebar': should_update_sidebar,
                        'show_bookings': True,
                        'bookings': bookings,
                        'action': 'update',
                        'new_date': entities.get('date'),
                        'new_time': entities.get('time')
                    })
                else:
                    # Just show bookings for selection
                    return jsonify({
                        'response': display_response,
                        'update_sidebar': should_update_sidebar,
                        'show_bookings': True,
                        'bookings': bookings,
                        'action': 'select'
                    })
            else:
                return jsonify({
                    'response': "I couldn't find any future bookings with that phone number. Please check the number and try again.",
                    'update_sidebar': should_update_sidebar
                })
            
        # Handle deleting booking
        elif task == 'deleting_booking' and entities.get('phone_number'):
            phone_number = entities.get('phone_number')
            bookings = get_bookings_by_phone(phone_number)
            
            if bookings:
                return jsonify({
                    'response': display_response,
                    'update_sidebar': should_update_sidebar,
                    'show_bookings': True,
                    'bookings': bookings,
                    'action': 'delete'
                })
            else:
                return jsonify({
                    'response': "I couldn't find any future bookings with that phone number. Please check the number and try again.",
                    'update_sidebar': should_update_sidebar
                })
        
        # Handle booking ticket
        elif task == 'booking_ticket':
            # Check if all entities are filled
            all_filled = all(entities.get(field) is not None for field in 
                ['name', 'phone_number', 'email', 'children_tickets', 'adult_tickets', 'date', 'time'])
            
            if all_filled:
                confirmation_text = f"""Please confirm your booking details:
                Name: {entities['name']}
                Phone: {entities['phone_number']}
                Email: {entities['email']}
                Child Tickets (under 18): {entities['children_tickets']}
                Adult Tickets (18+): {entities['adult_tickets']}
                Date: {entities['date']}
                Time: {entities['time']}"""
                
                return jsonify({
                    'response': display_response,
                    'update_sidebar': should_update_sidebar,
                    'show_confirmation': True,
                    'confirmation_text': confirmation_text,
                    'booking_details': entities,
                    'payment_completed': state.payment_completed
                })
        
        # Default response
        return jsonify({
            'response': display_response,
            'update_sidebar': should_update_sidebar
        })
        
    except json.JSONDecodeError:
        # If response is not valid JSON, just return it as is
        return jsonify({
            'response': response,
            'update_sidebar': should_update_sidebar
        })

@app.route('/confirm_booking', methods=['POST'])
def confirm_booking():
    """Handle booking confirmation and create payment order"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    booking_details = request.json.get('booking_details')
    print("\nReceived booking details:")
    print(booking_details)
    
    # Calculate total amount
    try:
        child_tickets = int(booking_details['children_tickets'])
        adult_tickets = int(booking_details['adult_tickets'])
        total_amount = (child_tickets * CHILD_TICKET_PRICE + 
                       adult_tickets * ADULT_TICKET_PRICE) * 100  # Convert to paise
        
        # Create Razorpay order
        order_data = {
            'amount': total_amount,
            'currency': 'INR',
            'receipt': f"booking_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'notes': {
                'name': booking_details['name'],
                'email': booking_details['email'],
                'phone': booking_details['phone_number'],
                'child_tickets': str(child_tickets),
                'adult_tickets': str(adult_tickets),
                'date': booking_details['date'],
                'time': booking_details['time']
            }
        }
        
        order = razorpay_client.order.create(data=order_data)
        
        return jsonify({
            'status': 'success',
            'order_id': order['id'],
            'amount': total_amount,
            'currency': 'INR',
            'key': "rzp_test_MnUkBLUn8EYdag"
        })
        
    except Exception as e:
        print(f"Error creating payment order: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to create payment order. Please try again.'
        }), 500

def generate_ticket_pdf(booking_details, payment_id):
    """Generate PDF ticket with booking details"""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        booking_id = booking_details.get("booking_id", "N/A")
        qr.add_data(booking_id)
        qr.make(fit=True)
        
        # Create QR code image and save it temporarily
        qr_img = qr.make_image(fill_color="black", back_color="white")
        temp_qr_path = "temp_qr.png"
        qr_img.save(temp_qr_path)

        c = canvas.Canvas(tmp.name, pagesize=letter)
        width, height = letter

        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, height - 80, "Museum Ticket Receipt")

        c.setFont("Helvetica", 12)
        y_position = height - 120

        fields = {
            "Booking ID": booking_details.get("booking_id", "N/A"),
            "Name": booking_details.get("name", "N/A"),
            "Phone Number": booking_details.get("phone_number", "N/A"),
            "Email": booking_details.get("email", "N/A"),
            "Children Tickets": booking_details.get("children_tickets", "N/A"),
            "Adult Tickets": booking_details.get("adult_tickets", "N/A"),
            "Date": booking_details.get("date", "N/A"),
            "Time": booking_details.get("time", "N/A"),
            "Payment ID": payment_id
        }

        for key, value in fields.items():
            c.drawString(100, y_position, f"{key}: {value}")
            y_position -= 25

        # Add QR code to the right side
        qr_size = 150  # Size of QR code in points
        qr_x = width - qr_size - 100  # 100 points from right margin
        qr_y = height - qr_size - 80  # Align with title
        c.drawImage(temp_qr_path, qr_x, qr_y, width=qr_size, height=qr_size)

        c.save()
        
        # Clean up the temporary QR code file
        os.remove(temp_qr_path)
        return tmp.name

def send_booking_confirmation(booking_details, payment_id):
    """Send booking confirmation email with PDF ticket"""
    try:
        # Create email content
        subject = "Museum Ticket Booking Confirmation"
        body = f"""Dear {booking_details['name']},

Thank you for booking tickets at our museum! Your tickets are attached to this email.

Please keep this email and bring the attached ticket when you visit.

Thank you for choosing our museum!"""

        # Create message
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = booking_details['email']
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        # Generate and attach PDF
        pdf_path = generate_ticket_pdf(booking_details, payment_id)
        with open(pdf_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename=museum_ticket_{booking_details['name']}.pdf"
            )
            msg.attach(part)

        # Send email
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, booking_details['email'], msg.as_string())

        # Clean up temporary PDF file
        os.unlink(pdf_path)
        return True

    except Exception as e:
        print(f"Error sending email: {e}")
        return False

@app.route('/payment_success', methods=['POST'])
def payment_success():
    """Handle successful payment and save booking"""
    try:
        payment_id = request.json.get('razorpay_payment_id')
        order_id = request.json.get('razorpay_order_id')
        signature = request.json.get('razorpay_signature')
        
        if not all([payment_id, order_id, signature]):
            raise ValueError("Missing payment information")
        
        # Verify payment signature
        razorpay_client.utility.verify_payment_signature({
            'razorpay_payment_id': payment_id,
            'razorpay_order_id': order_id,
            'razorpay_signature': signature
        })
        
        # Get order details
        order = razorpay_client.order.fetch(order_id)
        
        # Check payment status
        payment = razorpay_client.payment.fetch(payment_id)
        if payment['status'] != 'captured':
            raise ValueError(f"Payment not successful. Status: {payment['status']}")
        
        booking_details = order['notes']
        
        # Generate unique booking ID using date and time
        booking_timestamp = datetime.now()
        booking_id = booking_timestamp.strftime('BK%Y%m%d%H%M%S')
        
        # Standardize date format to YYYY-MM-DD
        try:
            # First try to parse the date assuming it's DD-MM-YYYY
            booking_date = datetime.strptime(booking_details['date'], '%d-%m-%Y')
            standardized_date = booking_date.strftime('%Y-%m-%d')
        except ValueError:
            try:
                # If that fails, try YYYY-MM-DD format
                datetime.strptime(booking_details['date'], '%Y-%m-%d')
                standardized_date = booking_details['date']
            except ValueError:
                # If both fail, raise an error
                raise ValueError("Invalid date format. Expected DD-MM-YYYY or YYYY-MM-DD")
        
        # Fix field name mismatches and add additional fields
        booking_details = {
            'booking_id': booking_id,
            'user_id': session.get('user_id'),
            'name': booking_details['name'],
            'phone_number': booking_details['phone'],
            'email': booking_details['email'],
            'children_tickets': booking_details['child_tickets'],
            'adult_tickets': booking_details['adult_tickets'],
            'date': standardized_date,  # Use standardized date format
            'time': booking_details['time'],
            'payment_id': payment_id,
            'booking_time': booking_timestamp.strftime('%d-%m-%Y %H:%M'),
            'visited': 'FALSE'
        }
        
        # Save booking to CSV
        if not os.path.exists('bookings'):
            os.makedirs('bookings')
        
        csv_file = 'bookings/museum_bookings.csv'
        file_exists = os.path.exists(csv_file)
        
        with open(csv_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['booking_id', 'user_id', 'name', 
                                                'phone_number', 'email', 'children_tickets', 
                                                'adult_tickets', 'date', 'time', 'payment_id', 
                                                'booking_time', 'visited'])
            if not file_exists:
                writer.writeheader()
            writer.writerow(booking_details)
        
        # Send confirmation email
        email_sent = send_booking_confirmation(booking_details, payment_id)
        
        # Mark payment as completed in chat state
        state = get_chat_state()
        state.payment_completed = True
        
        return jsonify({
            'status': 'success',
            'message': f'Payment successful! Your booking has been confirmed. Booking ID: {booking_id} ' +
                     ('A confirmation email has been sent to your email address.' if email_sent else 
                      'However, we could not send the confirmation email. Please save your booking ID.')
        })
        
    except Exception as e:
        print(f"Error processing payment: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Payment verification failed. Please contact support.'
        }), 500

def initialize_new_conversation(title):
    """Save a new conversation"""
    base_dir = "conversations"
    os.makedirs(base_dir, exist_ok=True)
    
    conversation_id = str(int(datetime.now().timestamp() * 1000))
    filename = os.path.join(base_dir, f"{conversation_id}.json")
    
    # Save initial conversation data
    conversation_data = {
        "conversation_id": conversation_id,
        "title": title,
        "date": datetime.now().strftime("%d-%m-%Y"),
        "time": datetime.now().strftime("%H:%M")
    }
    
    with open(filename, "w") as f:
        json.dump(conversation_data, f, indent=4)
    
    return filename

def update_conversation_file(title, conversation_history, filename):
    """Update an existing conversation"""
    conversation_id = os.path.splitext(os.path.basename(filename))[0]
    conversation_data = {
        "conversation_id": conversation_id,
        "title": title,
        "conversation_history": conversation_history,
        "date": datetime.now().strftime("%d-%m-%Y"),
        "time": datetime.now().strftime("%H:%M")
    }
    
    with open(filename, "w") as f:
        json.dump(conversation_data, f, indent=4)

@app.route('/get_conversations')
def get_conversations():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
        
    base_dir = "conversations"
    if not os.path.exists(base_dir):
        return jsonify([])
        
    conversations = []
    for filename in os.listdir(base_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(base_dir, filename)
            with open(filepath, 'r') as f:
                data = json.load(f)
                conversations.append({
                    'filepath': filepath,
                    'title': data.get('title', 'Untitled'),
                    'date': data.get('date', ''),
                    'time': data.get('time', '')
                })
                
    return jsonify(sorted(conversations, key=lambda x: f"{x['date']} {x['time']}", reverse=True))

@app.route('/load_conversation', methods=['POST'])
def load_conversation():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
        
    state = get_chat_state()
    filepath = request.json.get('filepath')
    
    with open(filepath, 'r') as f:
        data = json.load(f)
        state.conversation_history = data['conversation_history']
        state.conversation_title = data['title']
        state.filename = filepath
        
    formatted_history = []
    for msg in state.conversation_history:
        if msg['role'] != 'system':
            formatted_history.append({
                'type': 'user' if msg['role'] == 'user' else 'bot',
                'content': msg['content']
            })
            
    return jsonify({
        'status': 'success',
        'history': formatted_history
    })

@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id in chat_states:
        del chat_states[user_id]
    session.clear()
    return redirect(url_for('login'))

@app.route('/new_chat', methods=['POST'])
def new_chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
        
    state = get_chat_state()
    # Reset everything except user_id
    state.conversation_history = INITIAL_CONVERSATION_HISTORY.copy()
    state.conversation_title = None
    state.filename = None
    state.selected_booking_id = None
    state.payment_completed = False
    
    return jsonify({
        'status': 'success',
        'message': "Welcome to Smart Museum! I can help you book tickets, update bookings, or answer any questions about our exhibits. How may I assist you today?"
    })

@app.route('/log_payment_status', methods=['POST'])
def log_payment_status():
    """Log payment portal status to terminal"""
    status = request.json.get('status')
    print("\nPAYMENT PORTAL STATUS:")
    print("=" * 50)
    print(status)
    print("=" * 50)
    return jsonify({'status': 'success'})

@app.route('/get_bookings')
def get_bookings():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        # Read bookings CSV with proper data types
        bookings_df = pd.read_csv('bookings/museum_bookings.csv', dtype={
            'user_id': int,
            'visited': str  # Force 'visited' to stay as string
        })
        
        # Filter bookings for current user
        user_bookings = bookings_df[bookings_df['user_id'] == session['user_id']]
        
        # Convert to list of dictionaries
        bookings = user_bookings.to_dict('records')
        
        # Ensure 'visited' is always 'TRUE' or 'FALSE' string
        for booking in bookings:
            booking['visited'] = str(booking['visited']).upper()
        
        # Sort by booking time (most recent first)
        bookings.sort(key=lambda x: x['booking_time'], reverse=True)
        
        return jsonify(bookings)
        
    except Exception as e:
        print(f"Error getting bookings: {e}")
        return jsonify([])

def get_bookings_by_phone(phone_number):
    """Get all future bookings for a phone number"""
    try:
        # Read bookings CSV
        bookings_df = pd.read_csv('bookings/museum_bookings.csv', dtype={
            'phone_number': str,  # Force phone_number to be string
            'visited': str        # Force visited to be string
        })
        
        # Filter by phone number and not visited
        # Convert input phone number to string for comparison
        phone_number = str(phone_number)
        filtered = bookings_df[(bookings_df['phone_number'] == phone_number) & 
                              (bookings_df['visited'].str.upper() != 'TRUE')]
        
        # Check if booking date is in the future
        today = datetime.now().strftime('%Y-%m-%d')
        future_bookings = filtered[filtered['date'] >= today]
        
        return future_bookings.to_dict('records')
    except Exception as e:
        print(f"Error getting bookings by phone: {e}")
        import traceback
        print(traceback.format_exc())  # Print full stack trace
        return []

@app.route('/get_bookings_by_phone', methods=['POST'])
def get_bookings_by_phone_route():
    """API endpoint to get bookings by phone number"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    phone_number = request.json.get('phone_number')
    if not phone_number:
        return jsonify({'error': 'Phone number is required'}), 400
    
    bookings = get_bookings_by_phone(phone_number)
    return jsonify(bookings)

@app.route('/update_booking', methods=['POST'])
def update_booking():
    """Update an existing booking"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    booking_id = request.json.get('booking_id')
    new_date = request.json.get('date')
    new_time = request.json.get('time')
    
    if not all([booking_id, new_date, new_time]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        # Read bookings CSV
        bookings_df = pd.read_csv('bookings/museum_bookings.csv')
        
        # Find the booking
        booking_index = bookings_df[bookings_df['booking_id'] == booking_id].index
        if booking_index.empty:
            return jsonify({'error': 'Booking not found'}), 404
        
        # Update the booking
        bookings_df.loc[booking_index, 'date'] = new_date
        bookings_df.loc[booking_index, 'time'] = new_time
        
        # Save the updated CSV
        bookings_df.to_csv('bookings/museum_bookings.csv', index=False)
        
        return jsonify({
            'status': 'success',
            'message': f'Booking updated successfully to {new_date} at {new_time}'
        })
    except Exception as e:
        print(f"Error updating booking: {e}")
        return jsonify({'error': 'Failed to update booking'}), 500

@app.route('/delete_booking', methods=['POST'])
def delete_booking():
    """Delete an existing booking"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    booking_id = request.json.get('booking_id')
    
    if not booking_id:
        return jsonify({'error': 'Booking ID is required'}), 400
    
    try:
        # Read bookings CSV
        bookings_df = pd.read_csv('bookings/museum_bookings.csv')
        
        # Find the booking
        booking_index = bookings_df[bookings_df['booking_id'] == booking_id].index
        if booking_index.empty:
            return jsonify({'error': 'Booking not found'}), 404
        
        # Drop the booking
        bookings_df = bookings_df.drop(booking_index)
        
        # Save the updated CSV
        bookings_df.to_csv('bookings/museum_bookings.csv', index=False)
        
        return jsonify({
            'status': 'success',
            'message': 'Booking deleted successfully'
        })
    except Exception as e:
        print(f"Error deleting booking: {e}")
        return jsonify({'error': 'Failed to delete booking'}), 500

@app.route('/select_booking', methods=['POST'])
def select_booking_route():
    """Set the selected booking ID in the chat state"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    booking_id = request.json.get('booking_id')
    if not booking_id:
        return jsonify({'error': 'Booking ID is required'}), 400
    
    state = get_chat_state()
    state.selected_booking_id = booking_id
    
    # Find the booking details to add to conversation history
    try:
        bookings_df = pd.read_csv('bookings/museum_bookings.csv', dtype={
            'phone_number': str,
            'visited': str
        })
        
        booking = bookings_df[bookings_df['booking_id'] == booking_id].to_dict('records')
        if booking:
            booking_details = booking[0]
            
            # Add booking details to conversation history as system message
            booking_prompt = {
                "role": "system",
                "content": f"""
The user has selected the following booking:
Booking ID: {booking_details['booking_id']}
Name: {booking_details['name']}
Phone: {booking_details['phone_number']}
Email: {booking_details['email']}
Children Tickets: {booking_details['children_tickets']}
Adult Tickets: {booking_details['adult_tickets']}
Date: {booking_details['date']}
Time: {booking_details['time']}

The user may want to update or delete this booking. If they want to update it, you'll need to collect a new date and time.
If they want to delete it, confirm their intention before proceeding.
"""
            }
            
            state.conversation_history.append(booking_prompt)
    except Exception as e:
        print(f"Error adding booking details to conversation: {e}")
    
    return jsonify({
        'status': 'success',
        'message': 'Booking selected'
    })

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0',port=5000) 