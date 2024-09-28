from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_socketio import SocketIO, join_room, leave_room, send
from flask_sqlalchemy import SQLAlchemy
import os
import uuid
from datetime import datetime  # Add this for timestamps

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads/'
socketio = SocketIO(app)
db = SQLAlchemy(app)

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    groups = db.relationship('UserGroup', backref='user', lazy=True)

class UserGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Initialize the database
with app.app_context():
    db.create_all()

# Store online users
online_users = set()

# Index route
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form.get('username')
        group_id = request.form.get('group_id')

        if username and 1 <= len(username) <= 20:
            if username in online_users:
                flash('該用戶名已在線，請選擇其他名稱。', 'error')
            else:
                user = User.query.filter_by(username=username).first()
                if user:
                    flash('此用戶名已被使用，請選擇其他名稱。', 'error')
                else:
                    user = User(username=username)
                    db.session.add(user)
                    db.session.commit()
                    online_users.add(username)
                    session['user_id'] = user.id

                    if group_id:
                        return redirect(url_for('chat', group_id=group_id))
                    else:
                        group_id = str(uuid.uuid4())
                        return redirect(url_for('chat', group_id=group_id))
        else:
            flash('用戶名必須在1到20個字之間。', 'error')

    return render_template('index.html')

# Chat route
@app.route('/<group_id>')
def chat(group_id):
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('index'))

    user = User.query.get(user_id)

    if not UserGroup.query.filter_by(user_id=user.id, group_id=group_id).first():
        user_group = UserGroup(group_id=group_id, user_id=user.id)
        db.session.add(user_group)
        db.session.commit()

    return render_template('chat.html', username=user.username, group=group_id)

# Handle WebSocket events
@socketio.on('join')
def handle_join(data):
    username = data['username']
    group = data['group']
    join_room(group)
    send({'username': username, 'message': f'{username} 加入了群組', 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, to=group)
    socketio.emit('user_joined', {'username': username, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, to=group)

@socketio.on('leave')
def handle_leave(data):
    username = data['username']
    group = data['group']
    leave_room(group)
    online_users.discard(username)
    send({'username': username, 'message': f'{username} 離開了群組', 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, to=group)
    socketio.emit('user_left', {'username': username, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, to=group)

@socketio.on('message')
def handle_message(data):
    username = data['username']
    group = data['group']
    message = data['message']
    send({'username': username, 'message': message, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, to=group)

# Main function
if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=10000, allow_unsafe_werkzeug=True)
