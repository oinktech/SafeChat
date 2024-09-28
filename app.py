from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, join_room, leave_room, send
from flask_sqlalchemy import SQLAlchemy
import uuid

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'
socketio = SocketIO(app)
db = SQLAlchemy(app)

# 數據庫模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    groups = db.relationship('UserGroup', backref='user', lazy=True)

class UserGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# 儲存不同群組的訊息記錄
group_messages = {}

# 初始化數據庫
with app.app_context():
    db.create_all()

# 首頁 - 輸入用戶名
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form.get('username')
        if username:
            user = User.query.filter_by(username=username).first()
            if user is None:
                user = User(username=username)
                db.session.add(user)
                db.session.commit()
            session['user_id'] = user.id
            return redirect(url_for('profile'))

    return render_template('index.html')

# 個人資料頁面 - 顯示已加入的群組和更改用戶名
@app.route('/profile')
def profile():
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('index'))

    user = User.query.get(user_id)
    groups = [ug.group_id for ug in user.groups]
    return render_template('profile.html', user=user, groups=groups)

# 更新用戶名
@app.route('/update_username', methods=['POST'])
def update_username():
    user_id = session.get('user_id')
    new_username = request.form.get('new_username')
    if user_id and new_username:
        user = User.query.get(user_id)
        user.username = new_username
        db.session.commit()
    return redirect(url_for('profile'))

# 進入群組聊天
@app.route('/<group_id>')
def chat(group_id):
    user_id = session.get('user_id')
    if user_id is None:
        return redirect(url_for('index'))

    user = User.query.get(user_id)

    if group_id not in group_messages:
        group_messages[group_id] = []

    # 檢查用戶是否已加入該群組
    if not UserGroup.query.filter_by(user_id=user.id, group_id=group_id).first():
        user_group = UserGroup(group_id=group_id, user_id=user.id)
        db.session.add(user_group)
        db.session.commit()

    return render_template('chat.html', username=user.username, group=group_id, messages=group_messages[group_id])

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
    
    # 儲存訊息
    group_messages[group].append({'username': username, 'message': message})
    
    send({'username': username, 'message': message}, to=group)

# WebSocket事件處理 - 離開群組
@socketio.on('leave')
def handle_leave(data):
    username = data['username']
    group = data['group']
    leave_room(group)
    send(f'{username} 離開了群組', to=group)

if __name__ == '__main__':
    socketio.run(app, debug=True)
