# 🔐 AI Classroom Entry Monitor

An AI-powered classroom security system that recognizes registered students using face recognition and detects unauthorized persons in real time. The system automatically logs entries, generates security alerts, and triggers alarms through a Flask-based web application.

---

## ✨ Features

- 🎥 Real-time webcam monitoring
- 👤 Student face registration
- 🤖 AI-powered face recognition
- 🚨 Unauthorized person detection
- 🔔 Automatic security alarm
- 📋 Entry and attendance logs
- 📊 Dashboard with live statistics
- 🗄️ SQLite/PostgreSQL database support

---

## 🛠️ Tech Stack

| Category | Technology |
|----------|------------|
| Frontend | HTML, CSS, JavaScript, Bootstrap |
| Backend | Flask |
| AI | OpenRouter AI (Gemini Flash 1.5) |
| Computer Vision | OpenCV |
| Database | SQLite / PostgreSQL |
| ORM | SQLAlchemy |

---

## 📂 Project Structure

```text
AI-Classroom-Entry-Monitor/
│
├── app.py
├── ai_service.py
├── alarm_system.py
├── config.py
├── models.py
├── requirements.txt
│
├── templates/
├── static/
│   ├── uploads/
│   └── sounds/
│
└── logs/
```

---

## ⚙️ Installation

### Clone Repository

```bash
git clone https://github.com/your-username/AI-Classroom-Entry-Monitor.git

cd AI-Classroom-Entry-Monitor
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment

Create a `.env` file.

```env
OPENROUTER_API_KEY=your_api_key
FLASK_SECRET_KEY=your_secret_key
```

### Run Application

```bash
python app.py
```

Open

```
http://localhost:5000
```

---

## 🚀 Workflow

1. Register students with their photos.
2. AI extracts facial features.
3. Start webcam monitoring.
4. System compares detected faces with registered students.
5. Recognized students are logged.
6. Unknown persons trigger an alarm and create a security alert.

---

## 📸 Screenshots

| Dashboard | Student Registration |
|-----------|----------------------|
| Add Screenshot | Add Screenshot |

| Live Monitoring | Alerts |
|-----------------|--------|
| Add Screenshot | Add Screenshot |

---

## 📈 Future Improvements

- Email notifications
- Mobile application
- Multi-camera support
- Cloud deployment
- Attendance report export
- Role-based authentication

---

## 👨‍💻 Author

**Selva Vishva M**

- LinkedIn: https://linkedin.com/in/your-profile
- GitHub: https://github.com/selvavishva

---

## ⭐ Support

If you found this project useful, please consider giving it a ⭐ on GitHub.
