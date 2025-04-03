from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import qrcode
from PIL import Image
import io
import os

def generate_ticket_pdf(filename, details):
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    booking_id = details.get("booking_id", "N/A")
    qr.add_data(booking_id)
    qr.make(fit=True)
    
    # Create QR code image and save it temporarily
    qr_img = qr.make_image(fill_color="black", back_color="white")
    temp_qr_path = "temp_qr.png"
    qr_img.save(temp_qr_path)

    # Create PDF
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # Draw the title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, height - 80, "Museum Ticket Receipt")

    # Draw the details
    c.setFont("Helvetica", 12)
    y_position = height - 120  # Starting Y position

    # Define the details to include in the PDF
    fields = {
        "Name": details.get("name", "N/A"),
        "Phone Number": details.get("phone_number", "N/A"),
        "Email": details.get("email", "N/A"),
        "Children Tickets": details.get("children_tickets", "N/A"),
        "Adult Tickets": details.get("adult_tickets", "N/A"),
        "Date": details.get("date", "N/A"),
        "Time": details.get("time", "N/A"),
        "Booking ID": booking_id,
    }

    for key, value in fields.items():
        c.drawString(100, y_position, f"{key}: {value}")
        y_position -= 25  # Move text down

    # Add QR code to the right side
    qr_size = 150  # Size of QR code in points
    qr_x = width - qr_size - 100  # 100 points from right margin
    qr_y = height - qr_size - 80  # Align with title
    c.drawImage(temp_qr_path, qr_x, qr_y, width=qr_size, height=qr_size)

    c.save()
    
    # Clean up the temporary QR code file
    os.remove(temp_qr_path)
    
    print(f"PDF saved as {filename}")

# Example usage
details = {
    "name": "John Doe",
    "phone_number": "123-456-7890",
    "email": "johndoe@example.com",
    "children_tickets": "2",
    "adult_tickets": "3",
    "date": "2025-03-15",
    "time": "14:30",
    "booking_id": "1234567890"
}

generate_ticket_pdf("museum_ticket.pdf", details)
