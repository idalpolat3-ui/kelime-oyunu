from flask import render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db
from models import User, Word, WordSample
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from google import genai
import random

client = genai.Client(api_key='AIzaSyDZ9lfOUIqBz37BqngQPRO9CjI6-bj4M4s')

def get_next_review(correct_count):
    intervals = [1, 7, 30, 90, 180, 365]
    if correct_count < len(intervals):
        days = intervals[correct_count]
        return datetime.utcnow() + timedelta(days=days)
    return None

@app.route('/')
@login_required
def index():
    words = Word.query.filter_by(user_id=current_user.id).all()
    return render_template('index.html', words=words)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        flash('Kayit basarili!')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Kullanici adi veya sifre hatali!')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/add_word', methods=['POST'])
@login_required
def add_word():
    english = request.form['english']
    turkish = request.form['turkish']
    picture = request.form.get('picture', '')
    sample = request.form.get('sample', '')
    word = Word(english=english, turkish=turkish, picture=picture, user_id=current_user.id)
    db.session.add(word)
    db.session.flush()
    if sample:
        word_sample = WordSample(word_id=word.id, sample=sample)
        db.session.add(word_sample)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/quiz')
@login_required
def quiz():
    word = Word.query.filter_by(
        user_id=current_user.id,
        is_learned=False
    ).filter(Word.next_review <= datetime.utcnow()).first()
    if not word:
        return render_template('quiz.html', word=None)
    return render_template('quiz.html', word=word)

@app.route('/answer/<int:word_id>/<int:correct>')
@login_required
def answer(word_id, correct):
    word = Word.query.get(word_id)
    if correct:
        word.correct_count += 1
        next_review = get_next_review(word.correct_count)
        if next_review is None:
            word.is_learned = True
        else:
            word.next_review = next_review
    else:
        word.correct_count = 0
        word.next_review = datetime.utcnow()
    db.session.commit()
    return redirect(url_for('quiz'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        count = int(request.form['daily_count'])
        current_user.daily_word_count = count
        db.session.commit()
        flash('Ayarlar kaydedildi!')
    return render_template('settings.html', current_count=current_user.daily_word_count)

@app.route('/report')
@login_required
def report():
    total = Word.query.filter_by(user_id=current_user.id).count()
    learned = Word.query.filter_by(user_id=current_user.id, is_learned=True).count()
    not_learned = total - learned
    if total > 0:
        success_rate = round((learned / total) * 100, 1)
    else:
        success_rate = 0
    return render_template('report.html', total=total, learned=learned, not_learned=not_learned, success_rate=success_rate)

@app.route('/wordle')
@login_required
def wordle():
    words = Word.query.filter_by(user_id=current_user.id).all()
    if not words:
        flash('Once kelime eklemelisiniz!')
        return redirect(url_for('index'))
    word = random.choice(words)
    return render_template('wordle.html', target=word.english.upper())

@app.route('/wordle/check', methods=['POST'])
@login_required
def wordle_check():
    guess = request.form['guess'].upper()
    target = request.form['target'].upper()
    result = []
    for i, letter in enumerate(guess):
        if i < len(target) and letter == target[i]:
            result.append('green')
        elif letter in target:
            result.append('yellow')
        else:
            result.append('gray')
    return jsonify({'result': result, 'correct': guess == target})

@app.route('/wordchain', methods=['GET', 'POST'])
@login_required
def wordchain():
    story = None
    words_used = None
    if request.method == 'POST':
        try:
            words = request.form['words']
            prompt = f"Bu kelimeleri kullanarak kisa bir Ingilizce hikaye yaz ve Turkceye cevir: {words}"
            response = client.models.generate_content(model='gemini-2.0-flash-lite', contents=prompt)
            story = response.text
            words_used = words
        except Exception as e:
            story = f"Hata: API kotasi doldu veya baglanti sorunu. Lutfen daha sonra tekrar deneyin."
            words_used = request.form['words']
    return render_template('wordchain.html', story=story, words_used=words_used)


@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        username = request.form['username']
        new_password = request.form['new_password']
        user = User.query.filter_by(username=username).first()
        if user:
            user.password = generate_password_hash(new_password)
            db.session.commit()
            flash('Sifre basariyla guncellendi!')
            return redirect(url_for('login'))
        flash('Kullanici bulunamadi!')
    return render_template('forgot.html')



@app.route('/delete_word/<int:word_id>')
@login_required
def delete_word(word_id):
    word = Word.query.get(word_id)
    if word and word.user_id == current_user.id:
        WordSample.query.filter_by(word_id=word_id).delete()
        db.session.delete(word)
        db.session.commit()
    return redirect(url_for('index'))