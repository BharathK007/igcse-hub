import os

files = {
    "app.py": '''import os
import json
import random
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-12345')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///igcse.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
gemini_model = None
if GEMINI_AVAILABLE and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ Gemini initialized.")
    except Exception as e:
        print(f"⚠️ Gemini init failed: {e}")
        gemini_model = None

# ---------- Database Models ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    streak = db.Column(db.Integer, default=0)
    last_visit = db.Column(db.DateTime, default=datetime.utcnow)
    subjects = db.Column(db.Text, default='[]')
    concept_progress = db.Column(db.Text, default='{}')

class Concept(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(100), nullable=False)
    topic = db.Column(db.String(200), nullable=False)
    subtopic = db.Column(db.String(200))
    difficulty = db.Column(db.Integer, default=1)
    description = db.Column(db.Text)
    prerequisites = db.Column(db.Text, default='[]')

class FlashcardDeck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Flashcard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    deck_id = db.Column(db.Integer, db.ForeignKey('flashcard_deck.id'), nullable=False)
    term = db.Column(db.String(500), nullable=False)
    definition = db.Column(db.Text, nullable=False)
    known = db.Column(db.Boolean, default=False)

class QuizResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer)
    total = db.Column(db.Integer)
    date = db.Column(db.DateTime, default=datetime.utcnow)

# ---------- SUBJECTS ----------
SUBJECTS = {
    'Biology': {'code': '0610', 'icon': 'fa-dna', 'color': '#2ecc71', 'description': 'Cells, genetics, ecology'},
    'Chemistry': {'code': '0620', 'icon': 'fa-atom', 'color': '#3498db', 'description': 'Stoichiometry, organic, equilibria'},
    'Physics': {'code': '0625', 'icon': 'fa-flask', 'color': '#e74c3c', 'description': 'Mechanics, waves, electricity'},
    'Geography': {'code': '0460', 'icon': 'fa-globe', 'color': '#f39c12', 'description': 'Population, climate, development'},
    'ICT': {'code': '0417', 'icon': 'fa-laptop', 'color': '#9b59b6', 'description': 'Programming, networks, databases'},
    'Business Studies': {'code': '0450', 'icon': 'fa-chart-line', 'color': '#1abc9c', 'description': 'Marketing, finance, ops'},
    'Accounting': {'code': '0452', 'icon': 'fa-calculator', 'color': '#e67e22', 'description': 'Financial statements, ratios'},
    'Computer Science': {'code': '0478', 'icon': 'fa-code', 'color': '#2c3e50', 'description': 'Programming, algorithms, data'},
    'French': {'code': '0520', 'icon': 'fa-language', 'color': '#2980b9', 'description': 'Grammar, vocab, speaking'},
    'Literature': {'code': '0475', 'icon': 'fa-book-open', 'color': '#8e44ad', 'description': 'Poetry, prose, drama'},
    'English': {'code': '0500', 'icon': 'fa-book', 'color': '#27ae60', 'description': 'Language, writing, comprehension'},
    'History': {'code': '0470', 'icon': 'fa-history', 'color': '#d35400', 'description': 'World wars, revolutions'},
    'Global Perspectives': {'code': '0457', 'icon': 'fa-globe-americas', 'color': '#16a085', 'description': 'Global issues, research'},
    'Enterprise': {'code': '0454', 'icon': 'fa-lightbulb', 'color': '#f1c40f', 'description': 'Entrepreneurship, business ideas'},
    'Economics': {'code': '0455', 'icon': 'fa-chart-bar', 'color': '#2c3e50', 'description': 'Micro & macro economics'},
    'Additional Mathematics': {'code': '0606', 'icon': 'fa-plus-circle', 'color': '#e74c3c', 'description': 'Calculus, trigonometry'},
    'Arabic': {'code': '0508', 'icon': 'fa-language', 'color': '#f39c12', 'description': 'Arabic language, literature'},
    'Sociology': {'code': '0459', 'icon': 'fa-users', 'color': '#9b59b6', 'description': 'Social structures, families'},
    'Travel and Tourism': {'code': '0471', 'icon': 'fa-plane', 'color': '#1abc9c', 'description': 'Tourism industry, destinations'}
}

def create_concepts():
    concepts = []
    concepts.extend([
        {'subject': 'Biology', 'topic': 'Cell Biology', 'subtopic': 'Cell structure', 'difficulty': 1, 'description': 'Animal and plant cell organelles.', 'prerequisites': []},
        {'subject': 'Biology', 'topic': 'Cell Biology', 'subtopic': 'Mitosis', 'difficulty': 2, 'description': 'Process of mitosis.', 'prerequisites': []},
        {'subject': 'Biology', 'topic': 'Genetics', 'subtopic': 'DNA structure', 'difficulty': 2, 'description': 'Double helix, base pairing.', 'prerequisites': []},
        {'subject': 'Chemistry', 'topic': 'Stoichiometry', 'subtopic': 'Mole concept', 'difficulty': 2, 'description': 'Mole = mass / Mr.', 'prerequisites': []},
        {'subject': 'Physics', 'topic': 'Mechanics', 'subtopic': 'Newton\'s laws', 'difficulty': 2, 'description': 'F = ma.', 'prerequisites': []},
        {'subject': 'Geography', 'topic': 'Population', 'subtopic': 'Population growth', 'difficulty': 2, 'description': 'Birth, death, migration.', 'prerequisites': []},
        {'subject': 'English', 'topic': 'Writing', 'subtopic': 'Essay structure', 'difficulty': 2, 'description': 'Intro, body, conclusion.', 'prerequisites': []},
        {'subject': 'Business Studies', 'topic': 'Marketing', 'subtopic': 'The 4 Ps', 'difficulty': 2, 'description': 'Product, Price, Place, Promotion.', 'prerequisites': []},
        {'subject': 'Computer Science', 'topic': 'Programming', 'subtopic': 'Variables', 'difficulty': 1, 'description': 'Data types in Python.', 'prerequisites': []},
    ])
    return concepts

def init_db():
    db.create_all()
    if Concept.query.count() == 0:
        for c in create_concepts():
            concept = Concept(**c)
            concept.prerequisites = json.dumps(c['prerequisites'])
            db.session.add(concept)
        db.session.commit()
        print("✅ Concepts initialized.")

# ---------- Helpers ----------
def get_user_concepts(user):
    try:
        return json.loads(user.concept_progress)
    except:
        return {}

def update_concept_progress(user, concept_id, seen=False, completed=False, score=None):
    progress = get_user_concepts(user)
    key = str(concept_id)
    if key not in progress:
        progress[key] = {'seen': False, 'completed': False}
    if seen:
        progress[key]['seen'] = True
    if completed:
        progress[key]['completed'] = True
    if score is not None:
        progress[key]['last_quiz_score'] = score
    user.concept_progress = json.dumps(progress)
    db.session.commit()

def get_completed_concept_ids(user):
    progress = get_user_concepts(user)
    return [int(cid) for cid, data in progress.items() if data.get('completed', False)]

def get_recommended_concepts(user, limit=5):
    completed_ids = set(get_completed_concept_ids(user))
    all_concepts = Concept.query.all()
    available = []
    for c in all_concepts:
        if c.id in completed_ids:
            continue
        prereq = json.loads(c.prerequisites) if c.prerequisites else []
        if all(pid in completed_ids for pid in prereq):
            available.append(c)
    available.sort(key=lambda x: (x.difficulty, random.random()))
    return available[:limit]

def get_subject_progress(user, subject):
    all_concepts = Concept.query.filter_by(subject=subject).all()
    total = len(all_concepts)
    if total == 0:
        return 0, 0
    completed_ids = get_completed_concept_ids(user)
    completed = sum(1 for c in all_concepts if c.id in completed_ids)
    return completed, total

# ---------- Gemini ----------
def get_gemini_response(prompt):
    if gemini_model is None:
        return None
    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini error: {e}")
        return None

def generate_topical_paper(subject, topic, num_questions=5):
    if gemini_model is None:
        return None
    prompt = f"""You are an expert IGCSE teacher. Generate a topical past paper on "{subject}" topic "{topic}".
Include exactly {num_questions} questions with marks and answers.
Format as JSON array of objects with keys: "question", "marks", "answer".
Only output JSON."""
    response = get_gemini_response(prompt)
    if not response:
        return None
    match = re.search(r'\\[.*\\]', response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except:
            return None
    return None

def get_offline_response(query):
    q = query.lower()
    if any(w in q for w in ['math','quadratic']):
        return "Quadratic formula: x = [-b ± √(b²-4ac)] / 2a."
    if any(w in q for w in ['physics','force']):
        return "F = ma. Kinetic energy = ½mv²."
    if any(w in q for w in ['chemistry','mole']):
        return "n = m/Mr. Acids release H⁺."
    if any(w in q for w in ['biology','cell','dna']):
        return "Cell is basic unit. DNA double helix."
    return "I'm your IGCSE AI tutor. Please rephrase."

# ---------- ROUTES ----------
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        email = request.form.get('email','').strip()
        password = request.form.get('password','')
        if not all([username, email, password]):
            flash('All fields required.', 'danger')
            return redirect(url_for('register'))
        existing = User.query.filter((User.username==username)|(User.email==email)).first()
        if existing:
            flash('Username or email exists.', 'danger')
            return redirect(url_for('register'))
        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, email=email, password=hashed)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Choose subjects.', 'success')
        session['user_id'] = user.id
        session['username'] = user.username
        return redirect(url_for('onboarding'))
    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email','').strip()
    password = request.form.get('password','')
    user = User.query.filter_by(email=email).first()
    if user and bcrypt.check_password_hash(user.password, password):
        session['user_id'] = user.id
        session['username'] = user.username
        today = datetime.utcnow().date()
        last = user.last_visit.date() if user.last_visit else None
        if last == today - timedelta(days=1):
            user.streak += 1
        elif last != today:
            user.streak = 1
        user.last_visit = datetime.utcnow()
        db.session.commit()
        flash('Logged in!', 'success')
        return redirect(url_for('dashboard'))
    flash('Invalid credentials.', 'danger')
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/onboarding', methods=['GET','POST'])
def onboarding():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        selected = request.form.getlist('subjects')
        if selected:
            user.subjects = json.dumps(selected)
            db.session.commit()
            flash('Subjects saved!', 'success')
            return redirect(url_for('dashboard'))
        flash('Pick at least one subject.', 'danger')
    return render_template('onboarding.html', subjects=list(SUBJECTS.keys()))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    user = User.query.get(session['user_id'])
    try:
        user_subjects = json.loads(user.subjects) if user.subjects else []
    except:
        user_subjects = []
    if not user_subjects:
        return redirect(url_for('onboarding'))
    progress_data = {}
    for s in user_subjects:
        c, t = get_subject_progress(user, s)
        progress_data[s] = {'completed': c, 'total': t, 'percent': int(c/t*100) if t>0 else 0}
    total_all = sum(p['total'] for p in progress_data.values())
    completed_all = sum(p['completed'] for p in progress_data.values())
    overall_percent = int(completed_all/total_all*100) if total_all>0 else 0
    recommended = get_recommended_concepts(user, 5)
    all_concepts = Concept.query.all()
    seen_ids = set([int(cid) for cid, data in get_user_concepts(user).items() if data.get('seen', False)])
    unseen = [c for c in all_concepts if c.id not in seen_ids]
    unseen.sort(key=lambda x: x.difficulty)
    completed_ids = get_completed_concept_ids(user)
    recently_completed = Concept.query.filter(Concept.id.in_(completed_ids[-5:])).all() if completed_ids else []
    return render_template('dashboard.html',
                         user=user,
                         progress_data=progress_data,
                         overall_percent=overall_percent,
                         recommended=recommended,
                         unseen=unseen[:5],
                         recently_completed=recently_completed,
                         streak=user.streak,
                         total_concepts=total_all,
                         completed_concepts=completed_all)

@app.route('/subject/<subject_name>')
def view_subject(subject_name):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    user = User.query.get(session['user_id'])
    subject_data = SUBJECTS.get(subject_name)
    if not subject_data:
        flash('Subject not found.', 'danger')
        return redirect(url_for('dashboard'))
    concepts = Concept.query.filter_by(subject=subject_name).all()
    progress = get_user_concepts(user)
    concept_list = []
    for c in concepts:
        info = progress.get(str(c.id), {'seen': False, 'completed': False})
        concept_list.append({'concept': c, 'seen': info.get('seen', False), 'completed': info.get('completed', False)})
    c, t = get_subject_progress(user, subject_name)
    return render_template('subject.html', subject=subject_name, data=subject_data,
                         concepts=concept_list, completed=c, total=t)

@app.route('/concept/<int:concept_id>')
def view_concept(concept_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    concept = Concept.query.get(concept_id)
    if not concept:
        flash('Concept not found.', 'danger')
        return redirect(url_for('dashboard'))
    user = User.query.get(session['user_id'])
    progress = get_user_concepts(user)
    info = progress.get(str(concept_id), {'seen': False, 'completed': False})
    if not info.get('seen', False):
        update_concept_progress(user, concept_id, seen=True)
    prereq_ids = json.loads(concept.prerequisites) if concept.prerequisites else []
    prereq_concepts = Concept.query.filter(Concept.id.in_(prereq_ids)).all() if prereq_ids else []
    return render_template('concept.html', concept=concept, info=info, prereq_concepts=prereq_concepts)

@app.route('/mark_complete/<int:concept_id>', methods=['POST'])
def mark_complete(concept_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    update_concept_progress(user, concept_id, seen=True, completed=True)
    return jsonify({'success': True})

@app.route('/file/<subject>/<filename>')
def view_file(subject, filename):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    for folder in ['papers', 'study']:
        path = f'uploads/{subject}/{folder}/{filename}'
        if os.path.exists(path):
            if filename.lower().endswith('.pdf'):
                return render_template('pdf_viewer.html', subject=subject, filename=filename,
                                     file_path=f'/serve/{subject}/{filename}')
            else:
                return send_file(path, as_attachment=True)
    flash('File not found.', 'danger')
    return redirect(url_for('view_subject', subject_name=subject))

@app.route('/serve/<subject>/<filename>')
def serve_file(subject, filename):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    for folder in ['papers', 'study']:
        path = f'uploads/{subject}/{folder}/{filename}'
        if os.path.exists(path):
            return send_file(path)
    return 'File not found', 404

@app.route('/ai_chat', methods=['GET','POST'])
def ai_chat():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        user_msg = request.form.get('message', '').strip()
        if not user_msg:
            return jsonify({'response': 'Please type a question.'})
        # Check for topical paper request
        if any(k in user_msg.lower() for k in ['topical paper','generate','create questions','give me questions','question paper']):
            subject = None
            topic = None
            for s in SUBJECTS.keys():
                if s.lower() in user_msg.lower():
                    subject = s
                    break
            match = re.search(r'on\\s+([a-zA-Z\\s]+)', user_msg, re.IGNORECASE)
            if match:
                topic = match.group(1).strip()
            if not topic:
                topic = 'general'
            if not subject:
                subject = 'Biology'
            paper = generate_topical_paper(subject, topic, 5)
            if paper:
                response = f"📄 **Topical Paper: {subject} – {topic}**\\n\\n"
                for i, q in enumerate(paper, 1):
                    response += f"**Q{i}.** {q['question']} [{q.get('marks', '?')} marks]\\n"
                response += "\\n---\\n**Mark Scheme:**\\n"
                for i, q in enumerate(paper, 1):
                    response += f"**Q{i}.** {q.get('answer', 'Answer not provided.')}\\n"
                return jsonify({'response': response})
            else:
                return jsonify({'response': "I couldn't generate a topical paper. Please try again."})
        # Normal chat
        if gemini_model is not None:
            prompt = f"You are an expert IGCSE tutor. Answer: {user_msg}"
            resp = get_gemini_response(prompt)
            if resp:
                return jsonify({'response': resp})
        return jsonify({'response': get_offline_response(user_msg)})
    return render_template('ai_chat.html')

@app.route('/flashcards')
def flashcards():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    user = User.query.get(session['user_id'])
    decks = FlashcardDeck.query.filter_by(user_id=user.id).all()
    return render_template('flashcards.html', decks=decks, subjects=SUBJECTS)

@app.route('/create_deck', methods=['POST'])
def create_deck():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    subject = request.form.get('subject')
    name = request.form.get('name')
    if subject and name:
        deck = FlashcardDeck(user_id=session['user_id'], subject=subject, name=name)
        db.session.add(deck)
        db.session.commit()
        flash('Deck created!', 'success')
    else:
        flash('Fill all fields.', 'danger')
    return redirect(url_for('flashcards'))

@app.route('/add_card/<int:deck_id>', methods=['POST'])
def add_card(deck_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    deck = FlashcardDeck.query.get(deck_id)
    if not deck or deck.user_id != session['user_id']:
        flash('Deck not found.', 'danger')
        return redirect(url_for('flashcards'))
    term = request.form.get('term')
    definition = request.form.get('definition')
    if term and definition:
        card = Flashcard(deck_id=deck_id, term=term, definition=definition)
        db.session.add(card)
        db.session.commit()
        flash('Card added!', 'success')
    else:
        flash('Fill both fields.', 'danger')
    return redirect(url_for('view_deck', deck_id=deck_id))

@app.route('/view_deck/<int:deck_id>')
def view_deck(deck_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    deck = FlashcardDeck.query.get(deck_id)
    if not deck or deck.user_id != session['user_id']:
        flash('Deck not found.', 'danger')
        return redirect(url_for('flashcards'))
    cards = Flashcard.query.filter_by(deck_id=deck_id).all()
    return render_template('view_deck.html', deck=deck, cards=cards)

@app.route('/toggle_known/<int:card_id>', methods=['POST'])
def toggle_known(card_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    card = Flashcard.query.get(card_id)
    if card:
        deck = FlashcardDeck.query.get(card.deck_id)
        if deck and deck.user_id == session['user_id']:
            card.known = not card.known
            db.session.commit()
            return jsonify({'success': True, 'known': card.known})
    return jsonify({'error': 'Card not found'}), 404

@app.route('/quiz')
def quiz():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    user = User.query.get(session['user_id'])
    try:
        user_subjects = json.loads(user.subjects) if user.subjects else []
    except:
        user_subjects = []
    if not user_subjects:
        flash('Select subjects first.', 'info')
        return redirect(url_for('onboarding'))
    return render_template('quiz.html', subjects=user_subjects)

@app.route('/generate_quiz', methods=['POST'])
def generate_quiz():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    subject = request.form.get('subject')
    if not subject:
        return jsonify({'error': 'No subject'}), 400
    user = User.query.get(session['user_id'])
    concepts = Concept.query.filter_by(subject=subject).all()
    if not concepts:
        return jsonify({'error': 'No concepts'}), 404
    completed_ids = get_completed_concept_ids(user)
    completed_concepts = [c for c in concepts if c.id in completed_ids]
    not_completed = [c for c in concepts if c.id not in completed_ids]
    num_review = min(5, len(completed_concepts))
    num_challenge = min(5, len(not_completed))
    selected_review = random.sample(completed_concepts, num_review) if completed_concepts else []
    selected_challenge = random.sample(not_completed, num_challenge) if not_completed else []
    selected = selected_review + selected_challenge
    questions = []
    for c in selected:
        options = [c.description[:80]+"...", f"Related to {c.topic}", f"Another aspect", f"Not relevant"]
        random.shuffle(options)
        correct = options[0]
        questions.append({
            'question': f"Which best describes: {c.subtopic}?",
            'options': options,
            'correct': correct,
            'concept_id': c.id
        })
    return jsonify({'questions': questions})

@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    subject = data.get('subject')
    answers = data.get('answers', [])
    score = 0
    total = len(answers)
    for ans in answers:
        concept = Concept.query.get(ans['concept_id'])
        if concept and (concept.description in ans['selected'] or ans['selected'] in concept.description):
            score += 1
    result = QuizResult(user_id=session['user_id'], subject=subject, score=score, total=total)
    db.session.add(result)
    db.session.commit()
    user = User.query.get(session['user_id'])
    for ans in answers:
        update_concept_progress(user, ans['concept_id'], seen=True)
        if score/total >= 0.7:
            update_concept_progress(user, ans['concept_id'], completed=True)
    return jsonify({'score': score, 'total': total, 'percent': int(score/total*100) if total>0 else 0})

# ---------- Context Processor ----------
@app.context_processor
def utility_processor():
    def get_size(filepath):
        try:
            return os.path.getsize(filepath) // 1024
        except:
            return 0
    return dict(get_size=get_size)

# ---------- Init ----------
with app.app_context():
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
''',

    "requirements.txt": '''flask==2.2.3
flask-sqlalchemy==3.0.2
flask-bcrypt==1.0.1
gdown==4.6.0
tqdm==4.65.0
python-dotenv==1.0.0
gunicorn==20.1.0
google-generativeai==0.3.0
''',

    "Procfile": '''web: gunicorn app:app
''',

    "runtime.txt": '''python-3.11.0
''',

    ".gitignore": '''__pycache__/
*.pyc
*.db
*.sqlite3
.env
uploads/
!uploads/.gitkeep
venv/
env/
.idea/
.vscode/
*.log
.DS_Store
''',

    "README.md": '''# IGCSE Hub Pro

Adaptive learning platform with AI tutor, flashcards, quizzes, and past papers.

## Deploy

1. Install: `pip install -r requirements.txt`
2. Run: `python app.py`
3. Open http://localhost:5000

Set env vars: `SECRET_KEY` and `GEMINI_API_KEY`.
''',

    "download_papers.py": '''# Optional – run this to fetch your Google Drive files
print("Run: pip install gdown tqdm")
print("Then you can download your folders manually.")
'''
}

templates = {
    "templates/login.html": '''<!DOCTYPE html><html><head><title>Login - IGCSE Hub</title><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"><style>*{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',sans-serif;}body{background:linear-gradient(135deg,#f4f7fc 0%,#e9f0f8 100%);min-height:100vh;display:flex;justify-content:center;align-items:center;padding:20px;}.login-container{background:white;padding:50px;border-radius:30px;box-shadow:0 20px 60px rgba(0,0,0,0.1);width:100%;max-width:420px;}h1{text-align:center;color:#1e4a6b;}.subtitle{text-align:center;color:#7f8c8d;margin-bottom:30px;}.form-group{margin-bottom:20px;}.form-group label{display:block;margin-bottom:6px;color:#2c3e50;font-weight:600;}.form-group input{width:100%;padding:12px 15px;border:2px solid #e9f0f8;border-radius:12px;font-size:15px;}.btn{width:100%;padding:14px;background:#1e4a6b;color:white;border:none;border-radius:12px;font-size:16px;font-weight:600;cursor:pointer;}.btn:hover{background:#12344d;}.register-link{text-align:center;margin-top:20px;color:#7f8c8d;}.register-link a{color:#1e4a6b;text-decoration:none;font-weight:600;}.flash{padding:12px;border-radius:12px;margin-bottom:20px;}.flash.danger{background:#f8d7da;color:#721c24;}.flash.success{background:#d4edda;color:#155724;}.flash.info{background:#d1ecf1;color:#0c5460;}.demo-credentials{margin-top:20px;padding:15px;background:#f8f9fa;border-radius:12px;font-size:13px;color:#6c757d;}</style></head><body><div class="login-container"><h1><i class="fas fa-graduation-cap"></i> IGCSE Hub</h1><p class="subtitle">Sign in to access your study materials</p>{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for cat, msg in messages %}<div class="flash {{ cat }}">{{ msg }}</div>{% endfor %}{% endif %}{% endwith %}<form method="POST" action="{{ url_for('login') }}"><div class="form-group"><label>Email</label><input type="email" name="email" placeholder="student@example.com" required></div><div class="form-group"><label>Password</label><input type="password" name="password" placeholder="Enter your password" required></div><button type="submit" class="btn">Sign In</button></form><div class="register-link">Don't have an account? <a href="{{ url_for('register') }}">Create one</a></div><div class="demo-credentials"><i class="fas fa-info-circle"></i> Demo: <code>demo@igcse.com</code> / <code>password123</code></div></div></body></html>''',

    "templates/register.html": '''<!DOCTYPE html><html><head><title>Register - IGCSE Hub</title><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"><style>*{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',sans-serif;}body{background:linear-gradient(135deg,#f4f7fc 0%,#e9f0f8 100%);min-height:100vh;display:flex;justify-content:center;align-items:center;padding:20px;}.register-container{background:white;padding:50px;border-radius:30px;box-shadow:0 20px 60px rgba(0,0,0,0.1);width:100%;max-width:420px;}h1{text-align:center;color:#1e4a6b;}.subtitle{text-align:center;color:#7f8c8d;margin-bottom:30px;}.form-group{margin-bottom:20px;}.form-group label{display:block;margin-bottom:6px;color:#2c3e50;font-weight:600;}.form-group input{width:100%;padding:12px 15px;border:2px solid #e9f0f8;border-radius:12px;font-size:15px;}.btn{width:100%;padding:14px;background:#1e4a6b;color:white;border:none;border-radius:12px;font-size:16px;font-weight:600;cursor:pointer;}.btn:hover{background:#12344d;}.login-link{text-align:center;margin-top:20px;color:#7f8c8d;}.login-link a{color:#1e4a6b;text-decoration:none;font-weight:600;}.flash{padding:12px;border-radius:12px;margin-bottom:20px;}.flash.danger{background:#f8d7da;color:#721c24;}.flash.success{background:#d4edda;color:#155724;}.flash.info{background:#d1ecf1;color:#0c5460;}</style></head><body><div class="register-container"><h1><i class="fas fa-user-plus"></i> Create Account</h1><p class="subtitle">Join IGCSE Hub and start learning</p>{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for cat, msg in messages %}<div class="flash {{ cat }}">{{ msg }}</div>{% endfor %}{% endif %}{% endwith %}<form method="POST" action="{{ url_for('register') }}"><div class="form-group"><label>Username</label><input type="text" name="username" placeholder="Choose a username" required></div><div class="form-group"><label>Email</label><input type="email" name="email" placeholder="student@example.com" required></div><div class="form-group"><label>Password</label><input type="password" name="password" placeholder="Create a password" required></div><button type="submit" class="btn">Create Account</button></form><div class="login-link">Already have an account? <a href="{{ url_for('home') }}">Sign In</a></div></div></body></html>''',

    "templates/onboarding.html": '''<!DOCTYPE html><html><head><title>Choose Subjects - IGCSE Hub</title><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"><style>body{background:#f4f7fc;padding:20px;font-family:'Segoe UI',sans-serif;}.container{max-width:800px;margin:0 auto;background:white;padding:40px;border-radius:30px;box-shadow:0 10px 40px rgba(0,0,0,0.1);}h1{color:#1e4a6b;text-align:center;}.subjects-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:15px;margin:30px 0;}.subject-option{display:flex;align-items:center;gap:10px;padding:12px;background:#f9fcff;border-radius:12px;border:2px solid #e2ecf7;cursor:pointer;transition:0.2s;}.subject-option:hover{border-color:#b3cee6;}.subject-option input[type="checkbox"]{transform:scale(1.2);}.btn{background:#1e4a6b;color:white;border:none;padding:14px 30px;border-radius:40px;font-size:16px;font-weight:600;cursor:pointer;width:100%;}.btn:hover{background:#12344d;}.flash{padding:12px;border-radius:12px;margin-bottom:20px;}.flash.danger{background:#f8d7da;color:#721c24;}.flash.success{background:#d4edda;color:#155724;}</style></head><body><div class="container"><h1><i class="fas fa-hand-point-right"></i> Welcome, {{ session.username }}!</h1><p style="text-align:center;color:#7f8c8d;">Select the subjects you are studying.</p>{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for cat, msg in messages %}<div class="flash {{ cat }}">{{ msg }}</div>{% endfor %}{% endif %}{% endwith %}<form method="POST"><div class="subjects-grid">{% for subject in subjects %}<label class="subject-option"><input type="checkbox" name="subjects" value="{{ subject }}"> {{ subject }}</label>{% endfor %}</div><button type="submit" class="btn">Start Learning</button></form></div></body></html>''',

    "templates/dashboard.html": '''<!DOCTYPE html><html><head><title>Dashboard - IGCSE Hub</title><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"><style>*{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',sans-serif;}body{background:#f4f7fc;padding:20px;}.container{max-width:1400px;margin:0 auto;}.header{background:linear-gradient(135deg,#1e4a6b 0%,#12344d 100%);color:white;padding:25px 30px;border-radius:20px;display:flex;justify-content:space-between;align-items:center;margin-bottom:30px;}.header .user-info{display:flex;align-items:center;gap:15px;flex-wrap:wrap;}.header .user-info span{background:rgba(255,255,255,0.15);padding:8px 18px;border-radius:30px;}.header .user-info a{color:white;text-decoration:none;background:rgba(255,255,255,0.2);padding:8px 20px;border-radius:30px;}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;margin-bottom:30px;}.stat-card{background:white;padding:20px;border-radius:15px;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,0.05);}.stat-card .number{font-size:32px;font-weight:700;color:#1e4a6b;}.stat-card .label{color:#7f8c8d;font-size:14px;margin-top:5px;}.progress-bar{width:100%;height:8px;background:#e9f0f8;border-radius:10px;overflow:hidden;margin:5px 0;}.progress-bar .fill{height:100%;background:linear-gradient(90deg,#2ecc71,#27ae60);border-radius:10px;}.subject-progress{margin-bottom:15px;background:white;padding:15px;border-radius:15px;}.recommend-card{background:#f0f6fe;border-radius:15px;padding:15px;border-left:4px solid #1e4a6b;margin-bottom:20px;}.concept-tag{display:inline-block;background:#d3e2f0;padding:3px 12px;border-radius:20px;font-size:12px;margin:3px;}.btn{display:inline-block;background:#1e4a6b;color:white;padding:10px 25px;border-radius:40px;text-decoration:none;margin:5px;}.btn:hover{background:#12344d;}ul{list-style:none;padding:0;}ul li{padding:8px 0;border-bottom:1px solid #e9f0f8;}a{text-decoration:none;color:#1e4a6b;}@media(max-width:768px){.header{flex-direction:column;gap:15px;text-align:center;}}</style></head><body><div class="container"><div class="header"><h1><i class="fas fa-graduation-cap"></i> IGCSE Hub</h1><div class="user-info"><span><i class="fas fa-fire"></i> {{ streak }} day streak</span><span><i class="fas fa-user"></i> {{ user.username }}</span><a href="{{ url_for('logout') }}"><i class="fas fa-sign-out-alt"></i> Logout</a></div></div><div class="stats"><div class="stat-card"><div class="number">{{ completed_concepts }}/{{ total_concepts }}</div><div class="label">Concepts mastered</div></div><div class="stat-card"><div class="number">{{ overall_percent }}%</div><div class="label">Overall progress</div></div></div><h3>Your Subjects</h3>{% for subject, data in progress_data.items() %}<div class="subject-progress"><strong><a href="{{ url_for('view_subject', subject_name=subject) }}">{{ subject }}</a></strong> – {{ data.completed }}/{{ data.total }}<div class="progress-bar"><div class="fill" style="width: {{ data.percent }}%;"></div></div></div>{% endfor %}<h3><i class="fas fa-rocket"></i> Recommended Next</h3>{% if recommended %}<div class="recommend-card">{% for concept in recommended %}<a href="{{ url_for('view_concept', concept_id=concept.id) }}" style="display:block;padding:5px 0;border-bottom:1px solid #e2ecf7;"><span>{{ concept.topic }} – {{ concept.subtopic }}</span><span class="concept-tag">Difficulty {{ concept.difficulty }}</span></a>{% endfor %}</div>{% else %}<p>You've completed all concepts! 🎉</p>{% endif %}<h3><i class="fas fa-sparkles"></i> New Concepts to Explore</h3>{% if unseen %}<ul>{% for concept in unseen %}<li><a href="{{ url_for('view_concept', concept_id=concept.id) }}">{{ concept.topic }} – {{ concept.subtopic }}</a></li>{% endfor %}</ul>{% else %}<p>You've seen all concepts! Great job!</p>{% endif %}<h3><i class="fas fa-clock"></i> Recent Activity</h3>{% if recently_completed %}<ul>{% for concept in recently_completed %}<li>{{ concept.topic }} – {{ concept.subtopic }} ✅</li>{% endfor %}</ul>{% else %}<p>No concepts completed yet. Start learning!</p>{% endif %}<div style="margin-top:30px;display:flex;gap:15px;flex-wrap:wrap;"><a href="{{ url_for('quiz') }}" class="btn">🧪 Take a Quiz</a><a href="{{ url_for('ai_chat') }}" class="btn" style="background:#2c3e50;">🤖 AI Tutor</a><a href="{{ url_for('flashcards') }}" class="btn" style="background:#8e44ad;">📚 Flashcards</a></div></div></body></html>''',

    "templates/subject.html": '''<!DOCTYPE html><html><head><title>{{ subject }} - IGCSE Hub</title><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"><style>*{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',sans-serif;}body{background:#f4f7fc;padding:20px;}.container{max-width:1200px;margin:0 auto;}.header{background:linear-gradient(135deg,#1e4a6b 0%,#12344d 100%);color:white;padding:25px 30px;border-radius:20px;display:flex;justify-content:space-between;align-items:center;margin-bottom:30px;}.header a{color:white;text-decoration:none;}.back-btn{background:rgba(255,255,255,0.2);padding:8px 20px;border-radius:30px;}.back-btn:hover{background:rgba(255,255,255,0.3);}.progress-info{font-size:16px;margin-bottom:10px;}.progress-bar{width:100%;height:10px;background:#e9f0f8;border-radius:10px;overflow:hidden;margin-bottom:20px;}.progress-bar .fill{height:100%;background:linear-gradient(90deg,#2ecc71,#27ae60);border-radius:10px;}.concept-item{display:flex;justify-content:space-between;padding:15px;background:white;border-radius:15px;margin-bottom:10px;align-items:center;border:1px solid #e9f0f8;}.concept-item .status{font-size:14px;}.concept-item .status.completed{color:#2ecc71;font-weight:600;}.concept-item .status.seen{color:#f39c12;}.concept-item .status.new{color:#95a5a6;}.btn-sm{background:#1e4a6b;color:white;padding:5px 15px;border-radius:20px;text-decoration:none;font-size:14px;}.btn-sm:hover{background:#12344d;}</style></head><body><div class="container"><div class="header"><h1><i class="fas {{ data.icon }}" style="color:{{ data.color }}"></i> {{ subject }}</h1><a href="{{ url_for('dashboard') }}" class="back-btn">← Back</a></div><div class="progress-info">Progress: {{ completed }}/{{ total }} concepts</div><div class="progress-bar"><div class="fill" style="width: {{ (completed/total*100)|round|int if total>0 else 0 }}%;"></div></div><h3>Concepts</h3>{% for item in concepts %}<div class="concept-item"><div><strong>{{ item.concept.topic }}</strong> – {{ item.concept.subtopic }} <span style="font-size:12px;color:#7f8c8d;">(difficulty {{ item.concept.difficulty }})</span></div><div><span class="status {% if item.completed %}completed{% elif item.seen %}seen{% else %}new{% endif %}">{% if item.completed %}✅ Completed{% elif item.seen %}👀 Seen{% else %}📘 New{% endif %}</span>{% if not item.completed %}<a href="{{ url_for('view_concept', concept_id=item.concept.id) }}" class="btn-sm">Learn</a>{% endif %}</div></div>{% endfor %}</div></body></html>''',

    "templates/concept.html": '''<!DOCTYPE html><html><head><title>{{ concept.topic }} - IGCSE Hub</title><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"><style>body{background:#f4f7fc;padding:20px;font-family:'Segoe UI',sans-serif;}.container{max-width:700px;margin:0 auto;background:white;padding:30px;border-radius:30px;box-shadow:0 10px 30px rgba(0,0,0,0.05);}.badge{background:#d3e2f0;padding:4px 14px;border-radius:20px;font-size:14px;display:inline-block;margin:3px;}.btn{background:#1e4a6b;color:white;border:none;padding:12px 25px;border-radius:40px;cursor:pointer;margin:5px;font-size:16px;}.btn:hover{background:#12344d;}.btn-success{background:#2ecc71;}.btn-success:hover{background:#27ae60;}a{text-decoration:none;color:#1e4a6b;}.prereq-list{margin:15px 0;}</style></head><body><div class="container"><a href="{{ url_for('view_subject', subject_name=concept.subject) }}">← Back to {{ concept.subject }}</a><h1>{{ concept.topic }} – {{ concept.subtopic }}</h1><p><span class="badge">Difficulty {{ concept.difficulty }}</span></p><p><strong>Description:</strong> {{ concept.description }}</p><div class="prereq-list"><strong>Prerequisites:</strong>{% if prereq_concepts %}{% for prereq in prereq_concepts %}<span class="badge">{{ prereq.topic }}</span>{% endfor %}{% else %}<span class="badge">None</span>{% endif %}</div><div><form action="{{ url_for('mark_complete', concept_id=concept.id) }}" method="POST" style="display:inline;"><button type="submit" class="btn btn-success">✅ Mark as Completed</button></form><a href="{{ url_for('quiz') }}" class="btn">🧪 Take Quiz</a></div></div></body></html>''',

    "templates/ai_chat.html": '''<!DOCTYPE html><html><head><title>AI Tutor - IGCSE Hub</title><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"><style>body{background:#f4f7fc;padding:20px;font-family:'Segoe UI',sans-serif;}.container{max-width:800px;margin:0 auto;background:white;border-radius:30px;padding:30px;box-shadow:0 10px 30px rgba(0,0,0,0.05);}.chat-box{height:400px;overflow-y:auto;border:1px solid #e2ecf7;border-radius:15px;padding:20px;margin-bottom:20px;background:#fafcff;}.message{margin-bottom:15px;}.message.user{text-align:right;}.message.bot{text-align:left;}.message .bubble{display:inline-block;padding:10px 18px;border-radius:20px;max-width:80%;word-wrap:break-word;}.message.user .bubble{background:#1e4a6b;color:white;}.message.bot .bubble{background:#e9f0f8;color:#2c3e50;}.input-row{display:flex;gap:10px;margin-top:10px;}.input-row input{flex:1;padding:12px;border:2px solid #e9f0f8;border-radius:40px;font-size:16px;}.input-row button{padding:12px 25px;background:#1e4a6b;color:white;border:none;border-radius:40px;font-size:16px;cursor:pointer;}.input-row button:hover{background:#12344d;}.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:15px;}.toolbar button{background:#2c3e50;color:white;border:none;padding:8px 18px;border-radius:40px;cursor:pointer;}.toolbar button:hover{background:#1e2a3a;}.back{color:#1e4a6b;text-decoration:none;display:inline-block;margin-bottom:15px;}.back i{margin-right:5px;}.markdown{white-space:pre-wrap;}</style></head><body><div class="container"><a href="{{ url_for('dashboard') }}" class="back"><i class="fas fa-arrow-left"></i> Back</a><h2><i class="fas fa-robot"></i> AI Tutor</h2><p style="color:#7f8c8d;">Ask any IGCSE question – or ask me to generate a topical past paper!</p><div class="toolbar"><button onclick="generateTopical()"><i class="fas fa-file-alt"></i> Generate Topical Paper</button></div><div class="chat-box" id="chatBox"><div class="message bot"><div class="bubble">Hello! I'm your IGCSE AI tutor. Ask me anything, or say "Generate a topical paper on Biology: cell division"</div></div></div><div class="input-row"><input type="text" id="messageInput" placeholder="Type your question or request..." /><button id="sendBtn"><i class="fas fa-paper-plane"></i> Send</button></div></div><script>document.getElementById('sendBtn').addEventListener('click', sendMessage);document.getElementById('messageInput').addEventListener('keypress', function(e){if(e.key==='Enter') sendMessage();});function sendMessage(){const input=document.getElementById('messageInput');const msg=input.value.trim();if(!msg)return;addMessage('user',msg);input.value='';fetch('/ai_chat',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'message='+encodeURIComponent(msg)}).then(response=>response.json()).then(data=>{addMessage('bot',data.response);}).catch(()=>{addMessage('bot','Sorry, I encountered an error.');});}function addMessage(role,text){const chatBox=document.getElementById('chatBox');const div=document.createElement('div');div.className='message '+role;const bubble=document.createElement('div');bubble.className='bubble';bubble.innerHTML=text.replace(/\\n/g,'<br>');div.appendChild(bubble);chatBox.appendChild(div);chatBox.scrollTop=chatBox.scrollHeight;}function generateTopical(){const subject=prompt("Enter subject (e.g., Biology, Physics):","Biology");if(!subject)return;const topic=prompt("Enter topic (e.g., cell division, forces):","cell division");if(!topic)return;document.getElementById('messageInput').value=`Generate a topical paper on ${subject}: ${topic}`;sendMessage();}</script></body></html>''',

    "templates/flashcards.html": '''<!DOCTYPE html><html><head><title>Flashcards - IGCSE Hub</title><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"><style>body{background:#f4f7fc;padding:20px;font-family:'Segoe UI',sans-serif;}.container{max-width:900px;margin:0 auto;background:white;border-radius:30px;padding:30px;}.deck{padding:15px;border:1px solid #e2ecf7;border-radius:15px;margin:10px 0;display:flex;justify-content:space-between;align-items:center;}.btn{background:#1e4a6b;color:white;border:none;padding:10px 20px;border-radius:40px;cursor:pointer;text-decoration:none;display:inline-block;}.btn:hover{background:#12344d;}.btn-sm{padding:5px 15px;font-size:14px;}.form-group{margin:15px 0;}.form-group input,.form-group select{width:100%;padding:10px;border-radius:10px;border:1px solid #d3e2f0;}.back{color:#1e4a6b;text-decoration:none;}</style></head><body><div class="container"><a href="{{ url_for('dashboard') }}" class="back">← Back</a><h2><i class="fas fa-cards"></i> Flashcards</h2><h3>Your Decks</h3>{% if decks %}{% for deck in decks %}<div class="deck"><div><strong>{{ deck.name }}</strong> ({{ deck.subject }})</div><div><a href="{{ url_for('view_deck', deck_id=deck.id) }}" class="btn btn-sm">View</a></div></div>{% endfor %}{% else %}<p>No decks yet. Create one below!</p>{% endif %}<h3>Create New Deck</h3><form method="POST" action="{{ url_for('create_deck') }}"><div class="form-group"><label>Deck Name</label><input type="text" name="name" placeholder="e.g., Biology Terms" required></div><div class="form-group"><label>Subject</label><select name="subject" required>{% for subject in subjects.keys() %}<option value="{{ subject }}">{{ subject }}</option>{% endfor %}</select></div><button type="submit" class="btn">Create Deck</button></form></div></body></html>''',

    "templates/view_deck.html": '''<!DOCTYPE html><html><head><title>{{ deck.name }} - Flashcards</title><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"><style>body{background:#f4f7fc;padding:20px;font-family:'Segoe UI',sans-serif;}.container{max-width:800px;margin:0 auto;background:white;border-radius:30px;padding:30px;}.card{border:1px solid #e2ecf7;border-radius:15px;padding:20px;margin:10px 0;background:#fafcff;}.card .known{color:#2ecc71;font-weight:600;}.btn{background:#1e4a6b;color:white;border:none;padding:8px 18px;border-radius:40px;cursor:pointer;margin:5px;text-decoration:none;display:inline-block;}.btn:hover{background:#12344d;}.btn-sm{padding:4px 12px;font-size:13px;}.form-group{margin:15px 0;}.form-group input{width:100%;padding:10px;border-radius:10px;border:1px solid #d3e2f0;}.back{color:#1e4a6b;text-decoration:none;}</style></head><body><div class="container"><a href="{{ url_for('flashcards') }}" class="back">← Back to Decks</a><h2>{{ deck.name }}</h2><p>Subject: {{ deck.subject }}</p><h3>Cards</h3>{% if cards %}{% for card in cards %}<div class="card"><div><strong>{{ card.term }}</strong></div><div>{{ card.definition }}</div><div><span class="known">{% if card.known %}✅ Known{% else %}❓ Learning{% endif %}</span><button class="btn btn-sm toggle-known" data-id="{{ card.id }}">Toggle Known</button></div></div>{% endfor %}{% else %}<p>No cards yet. Add one below.</p>{% endif %}<h3>Add a Card</h3><form method="POST" action="{{ url_for('add_card', deck_id=deck.id) }}"><div class="form-group"><label>Term</label><input type="text" name="term" placeholder="e.g., Photosynthesis" required></div><div class="form-group"><label>Definition</label><input type="text" name="definition" placeholder="e.g., Process by which plants make food" required></div><button type="submit" class="btn">Add Card</button></form></div><script>document.querySelectorAll('.toggle-known').forEach(btn=>{btn.addEventListener('click',function(){const id=this.dataset.id;fetch(`/toggle_known/${id}`,{method:'POST'}).then(r=>r.json()).then(data=>{if(data.success)location.reload();});});});</script></body></html>''',

    "templates/quiz.html": '''<!DOCTYPE html><html><head><title>Quiz - IGCSE Hub</title><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"><style>body{background:#f4f7fc;padding:20px;font-family:'Segoe UI',sans-serif;}.container{max-width:800px;margin:0 auto;background:white;border-radius:30px;padding:30px;}.question{margin:20px 0;padding:15px;border-radius:15px;border:1px solid #e2ecf7;}.options{display:flex;flex-direction:column;gap:10px;margin:10px 0;}.options button{padding:10px;border-radius:10px;border:1px solid #d3e2f0;background:#f9fcff;cursor:pointer;transition:0.2s;}.options button:hover{background:#e9f0f8;}.options button.selected{background:#1e4a6b;color:white;border-color:#1e4a6b;}.btn{background:#1e4a6b;color:white;border:none;padding:12px 25px;border-radius:40px;cursor:pointer;margin:5px;}.btn:hover{background:#12344d;}.result{margin-top:20px;padding:20px;background:#d4edda;border-radius:15px;display:none;}.back{color:#1e4a6b;text-decoration:none;}</style></head><body><div class="container"><a href="{{ url_for('dashboard') }}" class="back">← Back</a><h2><i class="fas fa-puzzle-piece"></i> Adaptive Quiz</h2><p style="color:#7f8c8d;">Select a subject to generate a quiz based on your progress.</p><form id="quizForm"><div class="form-group" style="margin:20px 0;"><label>Choose Subject:</label><select name="subject" id="subjectSelect" style="padding:10px;border-radius:10px;border:1px solid #d3e2f0;width:100%;">{% for subject in subjects %}<option value="{{ subject }}">{{ subject }}</option>{% endfor %}</select></div><button type="button" id="generateBtn" class="btn">Generate Quiz</button></form><div id="quizContainer" style="display:none;margin-top:30px;"></div><div id="resultContainer" class="result"></div></div><script>let currentQuestions=[];let currentSubject='';document.getElementById('generateBtn').addEventListener('click',function(){const subject=document.getElementById('subjectSelect').value;currentSubject=subject;fetch('/generate_quiz',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'subject='+encodeURIComponent(subject)}).then(r=>r.json()).then(data=>{if(data.error){alert(data.error);return;}currentQuestions=data.questions;renderQuiz(data.questions);document.getElementById('quizContainer').style.display='block';document.getElementById('resultContainer').style.display='none';});});function renderQuiz(questions){const container=document.getElementById('quizContainer');let html='';questions.forEach((q,idx)=>{html+=`<div class="question" data-idx="${idx}"><strong>Q${idx+1}: ${q.question}</strong><div class="options">`;q.options.forEach((opt,oi)=>{html+=`<button class="option-btn" data-q="${idx}" data-opt="${oi}">${opt}</button>`;});html+=`</div></div>`;});html+=`<button id="submitQuizBtn" class="btn">Submit Quiz</button>`;container.innerHTML=html;document.querySelectorAll('.option-btn').forEach(btn=>{btn.addEventListener('click',function(){const parent=this.closest('.question');parent.querySelectorAll('.option-btn').forEach(b=>b.classList.remove('selected'));this.classList.add('selected');});});document.getElementById('submitQuizBtn').addEventListener('click',submitQuiz);}function submitQuiz(){const container=document.getElementById('quizContainer');const answers=[];document.querySelectorAll('.question').forEach(q=>{const selected=q.querySelector('.option-btn.selected');if(selected){const qIdx=parseInt(q.dataset.idx);const optText=selected.textContent;const conceptId=currentQuestions[qIdx].concept_id;answers.push({concept_id:conceptId,selected:optText});}});if(answers.length===0){alert('Please answer at least one question.');return;}fetch('/submit_quiz',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({subject:currentSubject,answers:answers})}).then(r=>r.json()).then(data=>{const resultDiv=document.getElementById('resultContainer');resultDiv.style.display='block';resultDiv.innerHTML=`<h3>Your Score: ${data.score}/${data.total} (${data.percent}%)</h3><p>${data.percent>=70?'Great job! You\'ve mastered these concepts!':'Keep learning! Try again.'}</p><a href="{{ url_for('dashboard') }}" class="btn">Back to Dashboard</a>`;document.getElementById('quizContainer').style.display='none';});}</script></body></html>''',

    "templates/pdf_viewer.html": '''<!DOCTYPE html><html><head><title>{{ subject }} - {{ filename }}</title><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"><style>*{margin:0;padding:0;box-sizing:border-box;}body{background:#f0f2f5;font-family:'Segoe UI',sans-serif;}.toolbar{background:#1e4a6b;color:white;padding:12px 25px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100;}.toolbar a{color:white;text-decoration:none;padding:6px 16px;border-radius:30px;background:rgba(255,255,255,0.15);}.toolbar a:hover{background:rgba(255,255,255,0.25);}.pdf-container{width:100%;height:calc(100vh - 60px);display:flex;justify-content:center;align-items:center;padding:10px;}iframe{width:100%;height:100%;border:none;border-radius:8px;background:white;}@media(max-width:768px){.toolbar{flex-direction:column;gap:10px;padding:12px 15px;}}</style></head><body><div class="toolbar"><div><h3><i class="fas fa-file-pdf" style="color:#ff6b6b;"></i> {{ subject }} - {{ filename }}</h3></div><div><a href="{{ file_path }}" download><i class="fas fa-download"></i> Download</a><a href="{{ url_for('view_subject', subject_name=subject) }}"><i class="fas fa-arrow-left"></i> Back</a></div></div><div class="pdf-container"><iframe src="{{ file_path }}#toolbar=1&navpanes=1&scrollbar=1"></iframe></div></body></html>'''
}

static_files = {
    "static/style.css": "body.dark-mode { background: #1a1a2e; color: #e0e0e0; } .dark-mode .container { background: #16213e; }",
    "static/script.js": "document.addEventListener('DOMContentLoaded',function(){const toggle=document.getElementById('darkToggle');if(toggle){toggle.addEventListener('click',function(){document.body.classList.toggle('dark-mode');localStorage.setItem('theme',document.body.classList.contains('dark-mode')?'dark':'light');});if(localStorage.getItem('theme')==='dark'){document.body.classList.add('dark-mode');}}});"
}

# Create folder structure
def create_project():
    base = "igcse-hub"
    os.makedirs(base, exist_ok=True)
    os.makedirs(os.path.join(base, "templates"), exist_ok=True)
    os.makedirs(os.path.join(base, "static"), exist_ok=True)

    for fname, content in files.items():
        with open(os.path.join(base, fname), 'w') as f:
            f.write(content)
    for fname, content in templates.items():
        with open(os.path.join(base, fname), 'w') as f:
            f.write(content)
    for fname, content in static_files.items():
        with open(os.path.join(base, fname), 'w') as f:
            f.write(content)
    print(f"✅ Project created in '{base}'")
    print("📁 Next steps:")
    print("  cd igcse-hub")
    print("  pip install -r requirements.txt")
    print("  python app.py")
    print("  Then visit http://localhost:5000")
    print("🔐 Remember to set environment variables: SECRET_KEY and GEMINI_API_KEY")

if __name__ == "__main__":
    create_project()