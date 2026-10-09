import datetime
import random
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "bloom_bank_super_secret_key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# User Account Model
class Account(db.Model):

  id = db.Column(db.Integer, primary_key=True)
  full_name = db.Column(db.String(100), nullable=False)
  age = db.Column(db.Integer, nullable=False)
  dob = db.Column(db.String(20), nullable=False)
  gender = db.Column(db.String(10), nullable=False)
  phone = db.Column(db.String(20), nullable=False)
  email = db.Column(db.String(100), nullable=False)
  nin = db.Column(db.String(11), nullable=True)
  bvn = db.Column(db.String(11), nullable=True)
  account_number = db.Column(db.String(10), unique=True, nullable=False)
  card_number = db.Column(db.String(16), unique=True, nullable=False)
  pin = db.Column(db.String(4), nullable=False)
  balance = db.Column(db.Float, default=0.0)


# Transaction Model for Receipt Logging
class Transaction(db.Model):

  id = db.Column(db.Integer, primary_key=True)
  account_id = db.Column(
      db.Integer, db.ForeignKey('account.id'), nullable=False
  )
  trans_type = db.Column(db.String(50), nullable=False)
  amount = db.Column(db.Float, nullable=False)
  balance_after = db.Column(db.Float, nullable=False)
  timestamp = db.Column(db.DateTime, default=datetime.datetime.now)


# Create database tables
with app.app_context():
  db.create_all()


@app.route('/')
def home():
  return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
  if request.method == 'POST':
    full_name = request.form['full_name']
    age = int(request.form['age'])
    dob = request.form['dob']
    gender = request.form['gender']
    phone = request.form['phone']
    email = request.form['email']
    nin = request.form['nin']
    bvn = request.form['bvn']
    pin = request.form['pin']

    has_nin = len(nin) == 11 and nin.isdigit()
    has_bvn = len(bvn) == 11 and bvn.isdigit()

    if age < 18 and not (has_nin or has_bvn):
      flash(
          'Applicants under 18 must provide a valid 11-digit NIN or BVN.',
          'danger',
      )
      return redirect(url_for('register'))

    acc_num = ''.join([str(random.randint(0, 9)) for _ in range(10)])
    card_num = ''.join([str(random.randint(0, 9)) for _ in range(16)])

    new_acc = Account(
        full_name=full_name,
        age=age,
        dob=dob,
        gender=gender,
        phone=phone,
        email=email,
        nin=nin,
        bvn=bvn,
        account_number=acc_num,
        card_number=card_num,
        pin=pin,
    )
    db.session.add(new_acc)
    db.session.commit()

    flash(
        f'Account created! Card Number: {card_num} | Account Number: {acc_num}',
        'success',
    )
    return redirect(url_for('home'))

  return render_template('register.html')


@app.route('/login', methods=['POST'])
def login():
  card_number = request.form.get('card_number', '')
  pin = request.form.get('pin', '')

  user = Account.query.filter_by(card_number=card_number, pin=pin).first()
  if user:
    session['user_id'] = user.id
    return redirect(url_for('dashboard'))

  flash('Invalid Card Number or PIN.', 'danger')
  return redirect(url_for('home'))


@app.route('/dashboard')
def dashboard():
  if 'user_id' not in session:
    return redirect(url_for('home'))

  user = Account.query.get(session['user_id'])
  if not user:
    session.pop('user_id', None)
    return redirect(url_for('home'))

  try:
    recent_transactions = (
        Transaction.query.filter_by(account_id=user.id)
        .order_by(Transaction.timestamp.desc())
        .limit(5)
        .all()
    )
  except Exception:
    recent_transactions = []

  return render_template(
      'dashboard.html', user=user, transactions=recent_transactions
  )


@app.route('/deposit', methods=['POST'])
def deposit():
  if 'user_id' not in session:
    return redirect(url_for('home'))

  amount = float(request.form.get('amount', 0))
  user = Account.query.get(session['user_id'])

  if amount <= 0:
    flash('Deposit amount must be greater than zero.', 'danger')
  else:
    user.balance += amount
    tx = Transaction(
        account_id=user.id,
        trans_type='DEPOSIT',
        amount=amount,
        balance_after=user.balance,
    )
    db.session.add(tx)
    db.session.commit()
    flash(f'Successfully deposited ₦{amount:,.2f}!', 'success')
    return redirect(url_for('receipt', transaction_id=tx.id))

  return redirect(url_for('dashboard'))


@app.route('/withdraw', methods=['POST'])
def withdraw():
  if 'user_id' not in session:
    return redirect(url_for('home'))

  amount = float(request.form.get('amount', 0))
  user = Account.query.get(session['user_id'])

  if amount <= 0:
    flash('Withdrawal amount must be greater than zero.', 'danger')
  elif amount > user.balance:
    flash('Insufficient funds available.', 'danger')
  else:
    user.balance -= amount
    tx = Transaction(
        account_id=user.id,
        trans_type='WITHDRAWAL',
        amount=amount,
        balance_after=user.balance,
    )
    db.session.add(tx)
    db.session.commit()
    flash(f'Please take your cash: ₦{amount:,.2f}', 'success')
    return redirect(url_for('receipt', transaction_id=tx.id))

  return redirect(url_for('dashboard'))


@app.route('/transfer', methods=['POST'])
def transfer():
  if 'user_id' not in session:
    return redirect(url_for('home'))

  recipient_acc = request.form.get('recipient_acc', '').strip()
  amount = float(request.form.get('amount', 0))
  user = Account.query.get(session['user_id'])
  recipient = Account.query.filter_by(account_number=recipient_acc).first()

  if not recipient:
    flash('Recipient account number not found.', 'danger')
  elif recipient.account_number == user.account_number:
    flash('Cannot transfer money to your own account.', 'danger')
  elif amount <= 0:
    flash('Transfer amount must be greater than zero.', 'danger')
  elif amount > user.balance:
    flash('Insufficient funds for this transfer.', 'danger')
  else:
    user.balance -= amount
    recipient.balance += amount

    tx_sender = Transaction(
        account_id=user.id,
        trans_type=f'TRANSFER TO {recipient.account_number}',
        amount=amount,
        balance_after=user.balance,
    )
    tx_recipient = Transaction(
        account_id=recipient.id,
        trans_type=f'TRANSFER FROM {user.account_number}',
        amount=amount,
        balance_after=recipient.balance,
    )

    db.session.add(tx_sender)
    db.session.add(tx_recipient)
    db.session.commit()

    flash(
        f'Transferred ₦{amount:,.2f} to {recipient.full_name} successfully!',
        'success',
    )
    return redirect(url_for('receipt', transaction_id=tx_sender.id))

  return redirect(url_for('dashboard'))


@app.route('/receipt/<int:transaction_id>')
def receipt(transaction_id):
  if 'user_id' not in session:
    return redirect(url_for('home'))

  tx = Transaction.query.get_or_404(transaction_id)
  user = Account.query.get(session['user_id'])
  if tx.account_id != user.id:
    flash('Unauthorized access to receipt.', 'danger')
    return redirect(url_for('dashboard'))

  return render_template('receipt.html', user=user, tx=tx)


@app.route('/logout')
def logout():
  session.pop('user_id', None)
  return redirect(url_for('home'))


if __name__ == '__main__':
  app.run(debug=True)