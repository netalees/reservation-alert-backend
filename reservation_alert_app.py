# reservation_alert_app.py

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from bs4 import BeautifulSoup
import smtplib
from datetime import datetime
from email.message import EmailMessage

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///alerts.db'
import os
print("🗂️  Using DB at:", os.path.abspath(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')))
db = SQLAlchemy(app)
scheduler = BackgroundScheduler()
scheduler.start()
print("Scheduler started!")
# Create DB and tables if they don’t exist
with app.app_context():
    db.create_all()
    print("✅ Created DB on Render (if needed)")

# Database model
class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_url = db.Column(db.String(500), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(20), nullable=False)
    party_size = db.Column(db.Integer, nullable=False)
    email = db.Column(db.String(100), nullable=False)
    notified = db.Column(db.Boolean, default=False)

# Email sending function
def send_email(recipient, subject, body):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = 'your_email@example.com'
    msg['To'] = recipient
    msg.set_content(body)

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login('your_email@example.com', 'your_app_password')
        server.send_message(msg)

import requests

ULTRAMSG_INSTANCE_ID = "111736"  # replace with your actual instance ID
ULTRAMSG_TOKEN = "your_token_here"  # replace with your actual token

import os
import requests

def send_whatsapp(phone_number, message):
    print(f"📲 Attempting to send WhatsApp to {phone_number} with message: {message}")
    
    url = f"https://api.ultramsg.com/{ULTRAMSG_INSTANCE_ID}/messages/chat"
    payload = {
        "token": ULTRAMSG_TOKEN,
        "to": phone_number,
        "body": message
    }
    try:
        response = requests.post(url, data=payload)
        print("📤 WhatsApp sent:", response.status_code, response.json())
    except Exception as e:
        print("❌ WhatsApp failed:", e)


# Check reservation availability
def check_availability():
    print("Checking availability at", datetime.now())
    with app.app_context():
        alerts = Alert.query.filter_by(notified=False).all()
        for alert in alerts:
            try:
                response = requests.get(alert.restaurant_url)
                soup = BeautifulSoup(response.text, 'html.parser')

                # ✅ Look for all time buttons that are NOT disabled
                available_buttons = soup.select('button')
                available_texts = [btn.get_text(strip=True) for btn in available_buttons if not btn.has_attr('disabled')]

                # 🧠 Try to extract a working booking link if possible
                booking_links = [btn.get('data-url') or btn.get('href') for btn in available_buttons if not btn.has_attr('disabled')]
                booking_links = [link for link in booking_links if link]  # filter out None values
                booking_url = booking_links[0] if booking_links else alert.restaurant_url

                if alert.time in available_texts:
                    msg = f"🎉 Table available for {alert.party_size} on {alert.date} at {alert.time}. Book: {booking_url}"

                    if alert.email:
                        send_email(alert.email, "Table Available!", msg)
                    if alert.phone_number:
                        print(f"📲 Phone number found: {alert.phone_number}, sending WhatsApp...")
                        send_whatsapp(alert.phone_number, msg)


                    alert.notified = True
                    db.session.commit()
                else:
                    print(f"🚫 {alert.time} not found in available times: {available_texts}")

            except Exception as e:
                print(f"Error checking availability: {e}")

scheduler.add_job(check_availability, 'interval', minutes=5, next_run_time=datetime.utcnow())


# API route to create alert
@app.route('/create_alert', methods=['POST'])
def create_alert():
    data = request.json
    new_alert = Alert(
        restaurant_url=data['restaurant_url'],
        date=data['date'],
        time=data['time'],
        party_size=data['party_size'],
        email=data['email']
    )
    db.session.add(new_alert)
    db.session.commit()
    return jsonify({'message': 'Alert created successfully!'}), 201
@app.route("/check_status", methods=["GET"])
def check_status():
    email = request.args.get("email")
    date = request.args.get("date")
    time = request.args.get("time")

    if not email or not date or not time:
        return jsonify({"error": "Missing parameters"}), 400

    alert = Alert.query.filter_by(email=email, date=date, time=time).first()

    if not alert:
        return jsonify({"status": "not_found"}), 404

    return jsonify({
        "status": "available" if alert.notified else "pending",
        "restaurant_url": alert.restaurant_url if alert.notified else None
    })

# Run the app
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        app.run(debug=False)  # <<< make sure debug is off

