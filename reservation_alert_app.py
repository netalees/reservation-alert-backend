from flask import Flask, request, jsonify  # Import request here
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from bs4 import BeautifulSoup
import smtplib
from datetime import datetime
from email.message import EmailMessage

# Initialize db, migrate, and scheduler globally
db = SQLAlchemy()  # Initialize db
migrate = Migrate()  # Initialize migrate
scheduler = BackgroundScheduler()  # Initialize scheduler

# Create Flask app inside a function to avoid circular imports
def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///alerts.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize app with db and migrate
    db.init_app(app)
    migrate.init_app(app, db)

    # Initialize scheduler
    scheduler.start()

    return app


# Initialize the app with the factory function
app = create_app()


# Model for alerts
class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_url = db.Column(db.String(500), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    time = db.Column(db.String(20), nullable=False)
    party_size = db.Column(db.Integer, nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)  # Add phone_number again
    notified = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Alert {self.restaurant_url} at {self.date} {self.time} for {self.party_size} people>"


# Route for creating alerts
@app.route('/create_alert', methods=['POST'])
def create_alert():
    try:
        data = request.json  # Now correctly using request object

        # Extract data from JSON
        restaurant_url = data.get("restaurant_url")
        date = data.get("date")
        time = data.get("time")
        party_size = data.get("party_size")
        email = data.get("email")
        phone_number = data.get("phone_number")

        # Create a new Alert object and add it to the database
        new_alert = Alert(
            restaurant_url=restaurant_url,
            date=date,
            time=time,
            party_size=party_size,
            email=email,
            phone_number=phone_number,
        )

        db.session.add(new_alert)
        db.session.commit()

        return {"message": "Alert created successfully!"}, 201

    except Exception as e:
        print(f"Error creating alert: {e}")
        return {"message": "Failed to create alert"}, 500


# Check reservation availability
def check_availability():
    print("🧠 Scheduler triggered - checking availability...")

    with app.app_context():
        alerts = Alert.query.filter_by(notified=False).all()  # Make sure alerts are fetched inside the context
        print(f"⚡ Found {len(alerts)} pending alerts")

        for alert in alerts:
            print(f"🔔 Alert details: {alert}")
            try:
                response = requests.get(alert.restaurant_url)
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for all time buttons that are NOT disabled
                available_buttons = soup.select('button')
                available_texts = [btn.get_text(strip=True) for btn in available_buttons if not btn.has_attr('disabled')]

                # Try to extract a working booking link if possible
                booking_links = [btn.get('data-url') or btn.get('href') for btn in available_buttons if not btn.has_attr('disabled')]
                booking_url = next((link for link in booking_links if link), alert.restaurant_url)

                if alert.time in available_texts:
                    print(f"✅ {alert.time} available!")
                    # Here, you would notify the user or mark it as notified in DB
                else:
                    print(f"🚫 {alert.time} not found in available times: {available_texts}")

            except Exception as e:
                print(f"⚠️ Error checking availability for alert {alert}: {e}")


scheduler.add_job(check_availability, 'interval', minutes=1, next_run_time=datetime.utcnow())
print("🧠 Scheduler job is added and running...")


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
        db.create_all()  # This will create tables
        app.run(debug=False)  # <<< make sure debug is off
