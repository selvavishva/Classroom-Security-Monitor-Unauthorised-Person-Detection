from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import cv2
import json
import base64
import numpy as np
from datetime import datetime, timedelta
import threading
import time

from config import Config
from models import db, Student, EntryLog, SystemAlert
from ai_service import AIService
from alarm_system import trigger_security_alarm, stop_security_alarm

app = Flask(__name__)
app.config.from_object(Config)
Config.init_app(app)

# Initialize extensions
db.init_app(app)
CORS(app)

# Initialize AI service
ai_service = AIService()

# Global variables for monitoring
monitoring_active = False
monitoring_thread = None
camera = None

def allowed_file(filename):
    """Check if file has allowed extension"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Main dashboard page"""
    # Get recent entry logs
    recent_entries = EntryLog.query.order_by(EntryLog.entry_time.desc()).limit(10).all()
    
    # Get active alerts
    active_alerts = SystemAlert.query.filter_by(is_resolved=False).order_by(
        SystemAlert.created_at.desc()
    ).limit(5).all()
    
    # Get student count
    total_students = Student.query.filter_by(is_active=True).count()
    
    # Get today's entries
    today = datetime.utcnow().date()
    today_entries = EntryLog.query.filter(
        db.func.date(EntryLog.entry_time) == today
    ).count()
    
    return render_template('index.html', 
                         recent_entries=recent_entries,
                         active_alerts=active_alerts,
                         total_students=total_students,
                         today_entries=today_entries,
                         monitoring_active=monitoring_active)

@app.route('/students')
def students():
    """Student management page"""
    students = Student.query.filter_by(is_active=True).all()
    return render_template('students.html', students=students)

@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
    """Add new student"""
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            student_id = request.form.get('student_id')
            email = request.form.get('email')
            phone = request.form.get('phone')
            
            # Check if student ID already exists
            existing_student = Student.query.filter_by(student_id=student_id).first()
            if existing_student:
                flash('Student ID already exists!', 'error')
                return redirect(url_for('add_student'))
            
            # Handle file upload
            if 'photo' not in request.files:
                flash('No photo uploaded!', 'error')
                return redirect(url_for('add_student'))
            
            file = request.files['photo']
            if file.filename == '':
                flash('No photo selected!', 'error')
                return redirect(url_for('add_student'))
            
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{student_id}_{file.filename}")
                photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Ensure upload directory exists
                os.makedirs(os.path.dirname(photo_path), exist_ok=True)
                file.save(photo_path)
                
                # Extract face features using AI
                features = ai_service.extract_face_features(photo_path)
                
                # Create new student
                student = Student(
                    name=name,
                    student_id=student_id,
                    email=email,
                    phone=phone,
                    photo_path=photo_path
                )
                
                # Store face features
                if features:
                    student.face_encoding = json.dumps(features)
                
                db.session.add(student)
                db.session.commit()
                
                flash('Student added successfully!', 'success')
                return redirect(url_for('students'))
            else:
                flash('Invalid file format!', 'error')
                
        except Exception as e:
            flash(f'Error adding student: {str(e)}', 'error')
            db.session.rollback()
    
    return render_template('add_student.html')

@app.route('/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    """Delete a student"""
    try:
        student = Student.query.get_or_404(student_id)
        student.is_active = False
        db.session.commit()
        flash('Student deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting student: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('students'))

@app.route('/start_monitoring', methods=['POST'])
def start_monitoring():
    """Start the face monitoring system"""
    global monitoring_active, monitoring_thread, camera
    
    try:
        if not monitoring_active:
            # Stop any existing camera
            if camera:
                camera.release()
                camera = None
            
            print("Attempting to initialize camera...")
            
            # Try different camera initialization methods
            camera_found = False
            camera_index = -1
            
            # Try multiple camera indices and backends
            backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]  # Windows backends
            
            for backend in backends:
                for i in range(5):  # Try camera indices 0-4
                    try:
                        print(f"Trying camera index {i} with backend {backend}")
                        camera = cv2.VideoCapture(i, backend)
                        
                        if camera.isOpened():
                            # Set basic camera properties
                            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                            camera.set(cv2.CAP_PROP_FPS, 15)  # Reduced FPS for stability
                            camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer
                            
                            # Test reading multiple frames to ensure stability
                            test_success = False
                            for test_attempt in range(3):
                                ret, test_frame = camera.read()
                                if ret and test_frame is not None and test_frame.size > 0:
                                    test_success = True
                                    print(f"Camera test successful - Frame size: {test_frame.shape}")
                                    break
                                time.sleep(0.1)
                            
                            if test_success:
                                camera_found = True
                                camera_index = i
                                print(f"✅ Camera {i} initialized successfully with backend {backend}")
                                print(f"Resolution: {camera.get(cv2.CAP_PROP_FRAME_WIDTH)}x{camera.get(cv2.CAP_PROP_FRAME_HEIGHT)}")
                                break
                        
                        camera.release()
                        camera = None
                        
                    except Exception as cam_error:
                        print(f"Camera {i} backend {backend} failed: {cam_error}")
                        if camera:
                            camera.release()
                            camera = None
                
                if camera_found:
                    break
            
            if not camera_found or camera is None:
                raise Exception("❌ No working camera found. Please check:\n1. Camera is connected\n2. Camera is not being used by another app\n3. Camera permissions are granted")
            
            monitoring_active = True
            
            # Start monitoring in a separate thread
            monitoring_thread = threading.Thread(target=monitor_faces, daemon=True)
            monitoring_thread.start()
            
            return jsonify({
                'status': 'success',
                'message': f'✅ Camera {camera_index} active - Monitoring started',
                'camera_info': {
                    'index': camera_index,
                    'width': int(camera.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    'height': int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    'fps': int(camera.get(cv2.CAP_PROP_FPS))
                }
            })
        else:
            return jsonify({'status': 'info', 'message': 'Monitoring already active'})
            
    except Exception as e:
        monitoring_active = False
        if camera:
            camera.release()
            camera = None
        error_msg = str(e)
        print(f"❌ Camera initialization failed: {error_msg}")
        return jsonify({'status': 'error', 'message': error_msg})

@app.route('/stop_monitoring', methods=['POST'])
def stop_monitoring():
    """Stop the face monitoring system"""
    global monitoring_active, camera
    
    try:
        monitoring_active = False
        
        if camera:
            camera.release()
            camera = None
        
        return jsonify({'status': 'success', 'message': 'Monitoring stopped'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error stopping monitoring: {str(e)}'})

@app.route('/get_camera_frame')
def get_camera_frame():
    """Get current camera frame as base64"""
    global camera
    
    try:
        if camera and camera.isOpened():
            ret, frame = camera.read()
            if ret:
                # Resize frame for better performance
                frame = cv2.resize(frame, (640, 480))
                
                # Convert to base64
                _, buffer = cv2.imencode('.jpg', frame)
                frame_base64 = base64.b64encode(buffer).decode('utf-8')
                
                return jsonify({
                    'status': 'success',
                    'frame': frame_base64,
                    'timestamp': datetime.utcnow().isoformat()
                })
            else:
                return jsonify({'status': 'error', 'message': 'Failed to read camera frame'})
        else:
            return jsonify({'status': 'error', 'message': 'Camera not initialized or not opened'})
        
    except Exception as e:
        print(f"Camera frame error: {e}")
        return jsonify({'status': 'error', 'message': f'Camera error: {str(e)}'})

@app.route('/monitoring_status')
def monitoring_status():
    """Get current monitoring status"""
    return jsonify({
        'active': monitoring_active,
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/entry_logs')
def entry_logs():
    """View entry logs"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    logs = EntryLog.query.order_by(EntryLog.entry_time.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('entry_logs.html', logs=logs)

@app.route('/alerts')
def alerts():
    """View system alerts"""
    alerts = SystemAlert.query.order_by(SystemAlert.created_at.desc()).all()
    return render_template('alerts.html', alerts=alerts)

@app.route('/resolve_alert/<int:alert_id>', methods=['POST'])
def resolve_alert(alert_id):
    """Resolve a system alert"""
    try:
        alert = SystemAlert.query.get_or_404(alert_id)
        alert.is_resolved = True
        alert.resolved_at = datetime.utcnow()
        db.session.commit()
        
        # Stop alarm when alert is resolved
        from alarm_system import stop_security_alarm
        stop_security_alarm()
        
        return jsonify({'status': 'success', 'message': 'Alert resolved and alarm stopped'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error resolving alert: {str(e)}'})

@app.route('/stop_alarm', methods=['POST'])
def stop_alarm():
    """Stop the security alarm"""
    try:
        from alarm_system import stop_security_alarm
        stop_security_alarm()
        return jsonify({'status': 'success', 'message': 'Alarm stopped'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error stopping alarm: {str(e)}'})

@app.route('/dashboard_stats')
def dashboard_stats():
    """Get real-time dashboard statistics"""
    try:
        # Get active alerts
        active_alerts = SystemAlert.query.filter_by(is_resolved=False).order_by(
            SystemAlert.created_at.desc()
        ).limit(5).all()
        
        # Get student count
        total_students = Student.query.filter_by(is_active=True).count()
        
        # Get today's entries
        today = datetime.utcnow().date()
        today_entries = EntryLog.query.filter(
            db.func.date(EntryLog.entry_time) == today
        ).count()
        
        # Get recent entries
        recent_entries = EntryLog.query.order_by(EntryLog.entry_time.desc()).limit(5).all()
        
        return jsonify({
            'status': 'success',
            'data': {
                'total_students': total_students,
                'today_entries': today_entries,
                'active_alerts_count': len(active_alerts),
                'monitoring_active': monitoring_active,
                'recent_entries': [entry.to_dict() for entry in recent_entries],
                'active_alerts': [alert.to_dict() for alert in active_alerts]
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error getting stats: {str(e)}'})

@app.route('/clear_all_data', methods=['POST'])
def clear_all_data():
    """Clear all system data (alerts, logs, etc.)"""
    try:
        # Stop monitoring and alarms first
        global monitoring_active, camera
        monitoring_active = False
        if camera:
            camera.release()
            camera = None
        
        from alarm_system import stop_security_alarm
        stop_security_alarm()
        
        # Clear all alerts
        SystemAlert.query.delete()
        
        # Clear all entry logs
        EntryLog.query.delete()
        
        # Commit changes
        db.session.commit()
        
        print("All system data cleared successfully")
        return jsonify({'status': 'success', 'message': 'All data cleared successfully'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error clearing data: {e}")
        return jsonify({'status': 'error', 'message': f'Error clearing data: {str(e)}'})

@app.route('/clear_alerts', methods=['POST'])
def clear_alerts():
    """Clear all resolved alerts"""
    try:
        # Delete all resolved alerts
        resolved_count = SystemAlert.query.filter_by(is_resolved=True).count()
        SystemAlert.query.filter_by(is_resolved=True).delete()
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Cleared {resolved_count} resolved alerts'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Error clearing alerts: {str(e)}'})

@app.route('/system_reset', methods=['POST'])
def system_reset():
    """Reset entire system to clean state"""
    try:
        # Stop everything
        global monitoring_active, camera
        monitoring_active = False
        if camera:
            camera.release()
            camera = None
        
        from alarm_system import stop_security_alarm
        stop_security_alarm()
        
        # Clear all data but keep students
        SystemAlert.query.delete()
        EntryLog.query.delete()
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'System reset successfully - Students preserved'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Error resetting system: {str(e)}'})

def monitor_faces():
    """Main face monitoring loop"""
    global monitoring_active, camera
    
    print("Face monitoring started...")
    
    # Track recent detections to prevent spam
    recent_detections = {}
    detection_cooldown = 10  # seconds
    
    with app.app_context():
        while monitoring_active and camera and camera.isOpened():
            try:
                ret, frame = camera.read()
                if not ret:
                    continue
                
                # Process frame for faces every 2 seconds to reduce load
                current_time = datetime.utcnow()
                
                # Process frame for faces
                detected_faces = ai_service.process_frame_for_faces(frame)
                
                if detected_faces:
                    for face_data in detected_faces:
                        # Check if face matches any known student
                        matched_student = None
                        best_match_score = 0.0
                        
                        if face_data.get('features'):
                            students = Student.query.filter_by(is_active=True).all()
                            
                            for student in students:
                                if student.face_encoding:
                                    stored_features = json.loads(student.face_encoding)
                                    similarity = ai_service.compare_faces(
                                        face_data['features'],
                                        stored_features
                                    )
                                    
                                    if similarity > best_match_score and similarity > 0.75:  # Increased threshold
                                        best_match_score = similarity
                                        matched_student = student
                        
                        # Determine detection key for cooldown
                        detection_key = matched_student.id if matched_student else 'unknown'
                        
                        # Check cooldown - only log if enough time has passed
                        if (detection_key not in recent_detections or
                            (current_time - recent_detections[detection_key]).total_seconds() > detection_cooldown):
                            
                            # Update recent detections
                            recent_detections[detection_key] = current_time
                            
                            # Create entry log
                            entry_log = EntryLog(
                                student_id=matched_student.id if matched_student else None,
                                is_recognized=matched_student is not None,
                                confidence_score=best_match_score if best_match_score > 0 else None,
                                entry_time=current_time
                            )
                            
                            db.session.add(entry_log)
                            db.session.commit()
                            
                            # Log the detection
                            if matched_student:
                                print(f"✅ Recognized: {matched_student.name} (Confidence: {best_match_score:.2f})")
                            else:
                                print("❌ Unknown person detected!")
                                
                                # Create alert for unknown person
                                alert = SystemAlert(
                                    alert_type='unknown_person',
                                    message=f'Unknown person detected at {current_time.strftime("%Y-%m-%d %H:%M:%S")}',
                                    severity='high'
                                )
                                
                                db.session.add(alert)
                                db.session.commit()
                                
                                # Trigger security alarm
                                trigger_security_alarm(
                                    alert_type='unknown_person',
                                    message=f'Unknown person detected at {current_time.strftime("%Y-%m-%d %H:%M:%S")}',
                                    severity='high'
                                )
                
                # Clean up old detections (older than 30 seconds)
                cutoff_time = current_time - timedelta(seconds=30)
                recent_detections = {k: v for k, v in recent_detections.items() if v > cutoff_time}
                
                # Longer delay to reduce processing load and improve stability
                time.sleep(2)
                
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(3)
        
        print("Face monitoring stopped.")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)