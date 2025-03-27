from reservation_alert_app import app, db, Alert

with app.app_context():
    db.drop_all()      # Optional: start fresh
    db.create_all()
    print("✅ Database created!")

