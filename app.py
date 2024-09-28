from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_socketio import SocketIO, join_room, leave_room, send
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length
import os
import uuid

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads/'
socketio = SocketIO(app)
db = SQLAlchemy(app)

# 確保上傳文件夾存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 數據庫模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    groups = db.relationship('UserGroup', backref='user', lazy=True)

class UserGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# 初始化數據庫
with app.app_context():
    db.create_all()

# 首頁 - 創建或加入房間
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form.get('username')
        group_id = request.form.get('group_id')

        if username and 1 <= len(username) <= 20:
            if User.query.filter_by(username=username).first():
                flash('此用戶名已被使用，請選擇其他名稱。', 'error')
            else:
                user = User(username=username)
                db.session.add(user)
                db.session.commit()
                session['user_id'] = user.id

                if group_id:
                    return redirect(url_for('chat', group_id=group_id))
                else:
                    group_id = str(uuid.uuid4())
                    return redirect(url_for('chat', group_id=group_id))
        else:
            flash('用戶名必須在1到20個字之間。', 'error')

    return render_template('index.html')

# 聊天房間
@app.route('/<group_id>')
def chat(group_id):
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('index'))

    user = User.query.get(user_id)

    # 檢查用戶是否已加入該群組
    if not UserGroup.query.filter_by(user_id=user.id, group_id=group_id).first():
        user_group = UserGroup(group_id=group_id, user_id=user.id)
        db.session.add(user_group)
        db.session.commit()

    return render_template('chat.html', username=user.username, group=group_id)

# WebSocket事件處理
@socketio.on('join')
def handle_join(data):
    username = data['username']
    group = data['group']
    join_room(group)
    send(f'{username} 加入了群組', to=group)

@socketio.on('message')
def handle_message(data):
    username = data['username']
    group = data['group']
    message = data['message']
    send({'username': username, 'message': message}, to=group)

# 上傳文件
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('未選擇文件', 'error')
        return redirect(url_for('chat', group_id=session['group_id']))

    file = request.files['file']
    if file.filename == '':
        flash('未選擇文件', 'error')
        return redirect(url_for('chat', group_id=session['group_id']))

    filename = f"{uuid.uuid4()}_{file.filename}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return redirect(url_for('chat', group_id=session['group_id']))

# 共享房間連結
@app.route('/share/<group_id>')
def share(group_id):
    return render_template('share.html', group_id=group_id)

# 下載文件
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    socketio.run(app, debug=True,host='0.0.0.0',port=10000)
