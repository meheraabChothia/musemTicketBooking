import fitz  # PyMuPDF
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import pandas as pd
import os
import tempfile

def check_ticket(pdf_path):
    try:
        # Open the PDF
        pdf_document = fitz.open(pdf_path)
        first_page = pdf_document[0]
        
        # Convert PDF page to image
        pix = first_page.get_pixmap()
        
        # Save image temporarily
        temp_img_path = tempfile.mktemp(suffix='.png')
        pix.save(temp_img_path)
        
        # Read the image with OpenCV
        image = cv2.imread(temp_img_path)
        
        # Clean up temporary image
        os.remove(temp_img_path)
        
        # Decode QR code
        decoded_objects = decode(image)
        
        if not decoded_objects:
            return "No QR code found in the ticket."
        
        # Get booking ID from QR code
        booking_id = decoded_objects[0].data.decode('utf-8')
        
        # Read CSV file
        df = pd.read_csv('bookings/museum_bookings.csv')
        
        # Find booking in CSV
        booking = df[df['booking_id'] == booking_id]
        
        if booking.empty:
            return "Invalid ticket: Booking not found."
        
        # Check if already visited
        if booking['visited'].iloc[0]:
            return "This ticket has already been used."
        
        # Update visited status
        df.loc[df['booking_id'] == booking_id, 'visited'] = True
        
        # Save updated CSV
        df.to_csv('bookings/museum_bookings.csv', index=False)
        
        return f"Valid ticket found!\nBooking ID: {booking_id}\nName: {booking['name'].iloc[0]}\nWelcome to the museum!"

    except Exception as e:
        return f"Error processing ticket: {str(e)}"

# Example usage
if __name__ == "__main__":
    pdf_path = "E:\major project\project files\\tickets\museum_ticket_meheraab.pdf"  # Path to the PDF ticket
    result = check_ticket(pdf_path)
    print(result)
