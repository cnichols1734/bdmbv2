from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime, timedelta
import shutil
import threading
import pytz
import logging
from logging.handlers import RotatingFileHandler
from sqlalchemy import inspect

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///new_database_V4.db'
app.config['SECRET_KEY'] = 'your_secret_key'

# Add logging configuration
if __name__ != '__main__':
    logging.basicConfig(level=logging.INFO)
    handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'bdmbmarket@gmail.com'
app.config['MAIL_PASSWORD'] = 'lfdrphxkskwyhicb'
app.config['MAIL_DEFAULT_SENDER'] = 'bdmbmarket@gmail.com'

# Initialize Flask-Mail
mail = Mail(app)

# Database migration logic
OLD_DB = 'new_database_V3.db'
NEW_DB = 'new_database_V4.db'
base_dir = os.path.abspath(os.path.dirname(__file__))
old_db_path = os.path.join(base_dir, OLD_DB)
new_db_path = os.path.join(base_dir, NEW_DB)

if os.path.exists(old_db_path) and not os.path.exists(new_db_path):
    shutil.copyfile(old_db_path, new_db_path)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///new_database_V4.db'

# Create absolute path for uploads
upload_folder = os.path.join(base_dir, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = upload_folder

# Ensure upload directory exists
os.makedirs(upload_folder, exist_ok=True)

db = SQLAlchemy(app)

# Define a function to ensure tables exist
def ensure_tables_exist():
    inspector = inspect(db.engine)
    existing_tables = inspector.get_table_names()
    
    if 'post_like' not in existing_tables:
        app.logger.info("Creating post_like table as part of database migration")
        db.metadata.tables['post_like'].create(db.engine)

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class PostLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_uuid = db.Column(db.String(36), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Composite unique constraint to prevent duplicate likes
    __table_args__ = (db.UniqueConstraint('post_id', 'user_uuid', name='_post_user_like_uc'),)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(20), nullable=False)
    photos = db.relationship('Photo', backref='post', lazy=True)
    comments = db.relationship('Comment', back_populates='post', cascade='all, delete')
    likes = db.relationship('PostLike', backref='post', lazy='dynamic', cascade='all, delete')
    uuid = db.Column(db.String(36), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    post_password = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    is_sold = db.Column(db.Boolean, default=False, nullable=False)  # New column

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    post = db.relationship('Post', back_populates='comments')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

def send_async_email(msg):
    """Send email asynchronously"""
    with app.app_context():
        try:
            mail.send(msg)
            app.logger.info(f"Email sent successfully to {msg.recipients}")
        except Exception as e:
            app.logger.error(f"Error sending email: {e}")


def send_comment_notification(post, comment):
    """Prepare and send email notification asynchronously"""
    if post.email:  # Only send if post has an email address
        try:
            # Convert UTC to Central Time
            central = pytz.timezone('America/Chicago')
            comment_time = comment.timestamp.replace(tzinfo=pytz.UTC).astimezone(central)

            # HTML version of the email
            html_content = f'''
            <!DOCTYPE html>
            <html>
            <head>
                <link href="https://fonts.googleapis.com/css2?family=Black+Ops+One&display=swap" rel="stylesheet">
                <style>
                    @import url('https://fonts.googleapis.com/css2?family=Black+Ops+One&display=swap');
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333333;
                        margin: 0;
                        padding: 0;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background-color: #3b82f6;
                        padding: 20px;
                        text-align: center;
                        border-radius: 5px 5px 0 0;
                    }}
                    .site-title {{
                        font-family: 'Black Ops One', Arial, sans-serif;
                        font-size: 24px;
                        margin: 0 0 10px 0;
                        color: #ffffff;
                        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
                    }}
                    .notification-title {{
                        font-size: 20px;
                        margin: 0;
                        font-weight: normal;
                        color: #ffffff;
                    }}
                    .content {{
                        background-color: #ffffff;
                        padding: 20px;
                        border: 1px solid #e5e7eb;
                        border-radius: 0 0 5px 5px;
                    }}
                    .comment-box {{
                        background-color: #f3f4f6;
                        padding: 15px;
                        border-radius: 5px;
                        margin: 20px 0;
                    }}
                    .button-container {{
                        text-align: center;
                        margin-top: 20px;
                    }}
                    .button {{
                        display: inline-block;
                        padding: 10px 20px;
                        background-color: #3b82f6;
                        color: #ffffff !important;
                        text-decoration: none;
                        border-radius: 5px;
                        font-weight: 500;
                    }}
                    .footer {{
                        text-align: center;
                        margin-top: 20px;
                        font-size: 12px;
                        color: #6b7280;
                    }}
                    @media (prefers-color-scheme: dark) {{
                        .header {{
                            background-color: #2563eb;
                        }}
                        .site-title, .notification-title {{
                            color: #ffffff !important;
                        }}
                        .content {{
                            background-color: #ffffff;
                        }}
                        .button {{
                            background-color: #2563eb;
                            color: #ffffff !important;
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1 class="site-title">Dads of Mont Belvieu Marketplace</h1>
                        <h2 class="notification-title">New Comment on Your Post</h2>
                    </div>
                    <div class="content">
                        <p>Hello,</p>
                        <p>You have received a new comment on your post "<strong>{post.title}</strong>".</p>

                        <div class="comment-box">
                            <p style="margin: 0;"><strong>Comment:</strong></p>
                            <p style="margin: 10px 0;">{comment.content}</p>
                            <p style="margin: 0; font-size: 12px; color: #6b7280;">
                                Posted {comment_time.strftime('%B %d, %Y at %I:%M %p')} CST
                            </p>
                        </div>

                        <div class="button-container">
                            <a href="{request.host_url}post/{post.id}" class="button">
                                View Post and Respond
                            </a>
                        </div>

                        <div class="footer">
                            <p>This email was sent from DMB Marketplace</p>
                            <p>This is an automated message, please do not reply directly to this email.</p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            '''

            # Plain text version as fallback
            text_content = f'''Dads of Mont Belvieu Marketplace
New Comment on Your Post

Hello,

A new comment has been added to your post "{post.title}".

Comment:
{comment.content}

Posted on {comment_time.strftime('%B %d, %Y at %I:%M %p')} CST

View your post and respond at:
{request.host_url}post/{post.id}

Best regards,
DMB Marketplace Team'''

            msg = Message(
                subject=f'DMB Marketplace: New Comment on Your Post - {post.title}',
                recipients=[post.email],
                body=text_content,
                html=html_content
            )

            # Create and start background thread for sending email
            thread = threading.Thread(
                target=send_async_email,
                args=(msg,)
            )
            thread.daemon = True  # Thread will exit when main program exits
            thread.start()
        except Exception as e:
            app.logger.error(f"Error preparing email notification: {e}")

@app.route('/')
def index():
    try:
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '')
        category = request.args.get('category', 'All')
        per_page = 9

        # Start with base query
        query = Post.query

        # Apply search filter if search term exists
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                db.or_(
                    Post.title.ilike(search_term),
                    Post.description.ilike(search_term),
                    Post.category.ilike(search_term)
                )
            )

        # Apply category filter if category is specified
        if category and category != 'All':
            query = query.filter(Post.category == category)

        # Apply final ordering
        query = query.order_by(Post.created_at.desc())

        # Apply pagination
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        posts = pagination.items
        total_pages = pagination.pages
        current_page = page
        
        # Get user_uuid from session for likes
        user_uuid = session.get('uuid')
        liked_post_ids = []
        
        # Try to get liked posts, but don't crash if post_like table doesn't exist yet
        try:
            if user_uuid:
                # Get list of post IDs that the user has liked
                liked_post_ids = [like.post_id for like in PostLike.query.filter_by(user_uuid=user_uuid).all()]
        except Exception as e:
            app.logger.error(f"Error getting liked posts: {e}")
            # Just use an empty list if there's an error

    except Exception as e:
        app.logger.error(f"Error in index route: {e}")
        posts = []
        total_pages = 1
        current_page = 1
        liked_post_ids = []

    return render_template('index.html',
                         posts=posts,
                         current_page=current_page,
                         total_pages=total_pages,
                         search=search,
                         category=category,
                         liked_post_ids=liked_post_ids)

@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def post(post_id):
    try:
        post = Post.query.get(post_id)
        if post is None:
            return render_template('post_not_found.html'), 404

        # Get user_uuid from session for likes
        user_uuid = session.get('uuid')
        user_liked = False
        
        # Try to check if user liked the post, but don't crash if post_like table doesn't exist yet
        try:
            if user_uuid:
                # Check if user liked this post
                user_liked = PostLike.query.filter_by(post_id=post.id, user_uuid=user_uuid).first() is not None
        except Exception as e:
            app.logger.error(f"Error checking if user liked post: {e}")
            # Just assume not liked if there's an error

        if request.method == 'POST':
            # Add comment
            comment_content = request.form['content']
            new_comment = Comment(content=comment_content, post_id=post.id)
            db.session.add(new_comment)
            db.session.commit()

            # Send email notification asynchronously
            send_comment_notification(post, new_comment)

            return redirect(url_for('post', post_id=post.id))
        return render_template('post.html', post=post, timedelta=timedelta, user_liked=user_liked)
    except Exception as e:
        app.logger.error(f"Error in post route: {e}")
        flash('An error occurred while processing your request.', 'error')
        return redirect(url_for('index'))

@app.route('/create_post', methods=['GET', 'POST'])
def create_post():
    if request.method == 'POST':
        try:
            user_uuid = session.get('uuid')
            if not user_uuid:
                user_uuid = str(uuid.uuid4())
                session['uuid'] = user_uuid

            title = request.form['title']
            description = request.form['description']
            price = request.form['price']
            category = request.form['category']
            post_password = request.form.get('post_password', '').strip()
            phone = request.form.get('phone', '').strip()
            email = request.form.get('email', '').strip()

            if post_password == '':
                post_password = None
            if phone == '':
                phone = None
            if email == '':
                email = None

            filenames = []
            for i in range(1, 5):
                photo = request.files.get(f'photo{i}')
                if photo and photo.filename:
                    filename = secure_filename(photo.filename)
                    photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    filenames.append(filename)

            if not filenames:
                app.logger.warning("No photos uploaded in create_post")
                return redirect(url_for('create_post'))

            new_post = Post(
                title=title,
                description=description,
                price=price,
                category=category,
                uuid=user_uuid,
                post_password=post_password,
                phone=phone,
                email=email
            )
            db.session.add(new_post)
            db.session.flush()

            for filename in filenames:
                new_photo = Photo(filename=filename, post_id=new_post.id)
                db.session.add(new_photo)

            db.session.commit()
            return redirect(url_for('index'))

        except Exception as e:
            app.logger.error(f"Error in create_post: {e}")
            db.session.rollback()
            flash('An error occurred while creating your post.', 'error')
            return redirect(url_for('create_post'))

    return render_template('create_post.html')

@app.route('/post/<int:post_id>/delete', methods=['POST'])
def delete_post(post_id):
    try:
        post = Post.query.get_or_404(post_id)
        input_password = request.form.get('post_password', '').strip()

        if post.post_password:
            if input_password != post.post_password:
                flash('Incorrect password. You are not authorized to delete this post.', 'error')
                return render_template('edit_post.html', post=post)
        else:
            flash('No password set, unable to verify ownership. Cannot delete.', 'error')
            return redirect(url_for('post', post_id=post.id))

        # If here, password is correct; proceed with deletion
        for photo in post.photos:
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo.filename)
            if os.path.exists(photo_path):
                os.remove(photo_path)
            db.session.delete(photo)

        db.session.delete(post)
        db.session.commit()
        flash('Your post has been deleted.', 'success')
        return redirect(url_for('index'))

    except Exception as e:
        app.logger.error(f"Error in delete_post: {e}")
        db.session.rollback()
        flash('An error occurred while deleting the post.', 'error')
        return redirect(url_for('post', post_id=post_id))

@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
def edit_post(post_id):
    try:
        post = Post.query.get_or_404(post_id)

        if request.method == 'POST':
            input_password = request.form.get('post_password', '').strip()

            if post.post_password is None:
                flash('This post has no password set and cannot be edited.', 'error')
                return redirect(url_for('post', post_id=post.id))

            if input_password != post.post_password:
                flash('Incorrect password. You are not authorized to edit this post.', 'error')
                return render_template('edit_post.html', post=post)

            # Update post with new fields
            post.title = request.form['title']
            post.description = request.form['description']
            post.price = request.form['price']
            post.category = request.form['category']
            post.phone = request.form.get('phone', '').strip() or None
            post.email = request.form.get('email', '').strip() or None

            db.session.commit()
            flash('Post updated successfully.', 'success')
            return redirect(url_for('post', post_id=post.id))

        return render_template('edit_post.html', post=post)

    except Exception as e:
        app.logger.error(f"Error in edit_post: {e}")
        db.session.rollback()
        flash('An error occurred while editing the post.', 'error')
        return redirect(url_for('post', post_id=post_id))

@app.route('/post/<int:post_id>/like', methods=['POST'])
def like_post(post_id):
    try:
        post = Post.query.get_or_404(post_id)
        
        # Ensure user has a UUID
        user_uuid = session.get('uuid')
        if not user_uuid:
            user_uuid = str(uuid.uuid4())
            session['uuid'] = user_uuid
        
        # Make sure post_like table exists before attempting to use it
        ensure_tables_exist()
            
        # Check if user already liked this post
        existing_like = PostLike.query.filter_by(post_id=post_id, user_uuid=user_uuid).first()
        
        if existing_like:
            # User already liked this post, so unlike it
            db.session.delete(existing_like)
            action = 'unliked'
        else:
            # User hasn't liked this post yet, add like
            new_like = PostLike(post_id=post_id, user_uuid=user_uuid)
            db.session.add(new_like)
            action = 'liked'
            
        db.session.commit()
        
        # If it's an AJAX request, return JSON response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            like_count = PostLike.query.filter_by(post_id=post_id).count()
            return {'success': True, 'action': action, 'likeCount': like_count}
            
        # Otherwise redirect back to the referring page
        referer = request.headers.get('Referer')
        if referer and (url_for('index') in referer or url_for('post', post_id=post.id) in referer):
            return redirect(referer)
        return redirect(url_for('post', post_id=post.id))
        
    except Exception as e:
        app.logger.error(f"Error in like_post route: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return {'success': False, 'error': 'An error occurred while processing your request.'}
        flash('An error occurred while processing your request.', 'error')
        return redirect(url_for('index'))

# Initialize database tables (including any new ones like PostLike)
with app.app_context():
    db.create_all()
    ensure_tables_exist()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5005, debug=True)
