from flask import Flask, request, render_template, redirect, session, send_file, make_response, jsonify
from io import BytesIO
from Crypt import Crypt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import os
import base64
import mysql.connector
import mimetypes
import shutil
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from docx import Document
import win32com.client as win32
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import ExtractiveSummaryAction
import requests
import uuid
import json
import shutil
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
import io

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

crypt = Crypt()

TEXT_ANALYTICS_KEY = "f03ea58106964b2683d7c7e6d1be4732"
TEXT_ANALYTICS_ENDPOINT = "https://textsummarysir.cognitiveservices.azure.com/"
TRANSLATOR_KEY = "3b71834a88f24263bbfd89860a924f10"
TRANSLATOR_ENDPOINT = "https://api.cognitive.microsofttranslator.com/"
TRANSLATOR_LOCATION = "centralindia"

def connect_to_mysql():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="secusto1"
    )

@app.route('/')
def homepage():
    return render_template('homepage.html')

@app.route('/personal')
def personal():
    return render_template('homePer.html')

@app.route('/law')
def law():
    return render_template('homeLaw.html')

@app.route('/finance')
def finance():
    return render_template('homeFin.html')
  
def validate_user(username, password):
    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM user WHERE username = %s AND password = %s", (username, password))
    user_id = cursor.fetchone()
    if user_id:
        cursor.execute("SELECT privatekey, publickey FROM encrypt WHERE uid = %s", (user_id[0],))
        keys = cursor.fetchone()
        if keys:
            private_key = serialization.load_pem_private_key(keys[0], password=None, backend=default_backend())
            public_key = serialization.load_pem_public_key(keys[1], backend=default_backend())
            session['private_key'] = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            session['public_key'] = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        else:
            private_key, public_key = crypt.generate_key_pair()
            private_key_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            cursor.execute("INSERT INTO encrypt (uid, privatekey, publickey) VALUES (%s, %s, %s)",
                           (user_id[0], private_key_bytes, public_key_bytes))
            conn.commit()
            session['private_key'] = private_key_bytes
            session['public_key'] = public_key_bytes
    conn.close()
    return user_id
  
@app.route('/userLogin', methods=['GET', 'POST'])
def login():
    session.clear()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_id = validate_user(username, password)
        if user_id:
            session['user_id'] = user_id[0]
            return redirect('/UploadDoclaw')
        else:
            login_message = "Invalid username or password"
            return render_template('loginLawUser.html', login_message=login_message)
    return render_template('loginLawUser.html')

@app.route('/create_account_luser', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']
        lawyerid = request.form['lawyerid']
        
        crypt = Crypt()
        private_key, public_key = crypt.generate_key_pair()
        
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        conn = connect_to_mysql()
        cursor = conn.cursor()
        sql = "INSERT INTO user (name, username, password) VALUES (%s, %s, %s)"
        val = (name, username, password)
        cursor.execute(sql, val)
        user_id = cursor.lastrowid
        
        sql = "INSERT INTO lawuser_rel (uid,lid) VALUES (%s, %s)"
        val = (user_id,lawyerid)
        cursor.execute(sql, val)
        
        sql = "INSERT INTO encrypt (uid, privatekey, publickey) VALUES (%s, %s, %s)"
        val = (user_id, private_key_bytes, public_key_bytes)
        cursor.execute(sql, val)
        
        conn.commit()
        conn.close()
        
        return redirect('/')
    return render_template('create_account_luser.html')

@app.route('/UploadDoclaw')
def upload_doc():
    user_id = session.get('user_id')
    if user_id:
        conn = connect_to_mysql()
        cursor = conn.cursor()
        cursor.execute("SELECT fid, filename FROM storeid WHERE uid = %s", (user_id,))
        files = cursor.fetchall()
        conn.close()
        return render_template('UploadDoclaw.html', user_id=user_id, files=files)
    else:
        return redirect('/')

@app.route('/upload', methods=['POST'])
def upload():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/')

    if 'file' not in request.files:
        return 'No file part'
    file = request.files['file']
    if file.filename == '':
        return 'No selected file'

    if file:
        file.save('uploads/' + file.filename)

        ipfs_hash = crypt.upload_pdf(f"uploads/{file.filename}")
        os.remove(f"uploads/{file.filename}")

        public_key = serialization.load_pem_public_key(session.get('public_key'), backend=default_backend())
        encrypted_ipfs_hash = crypt.encrypt_with_public_key(public_key, ipfs_hash)

        encrypted_ipfs_hash_str = base64.b64encode(encrypted_ipfs_hash).decode("utf-8")
        crypt.store_string(encrypted_ipfs_hash_str)

        id = crypt.getId()
        conn = connect_to_mysql()
        cursor = conn.cursor()

        sql = "INSERT INTO storeid (uid, fid, filename) VALUES (%s, %s, %s)"
        val = (user_id, id, file.filename)
        cursor.execute(sql, val)

        conn.commit()
        conn.close()

        return redirect('/UploadDoclaw')

@app.route('/retrieve/<id>', methods=['GET'])
def retrieve(id):
    filename = request.args.get('filename')
    
    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT filename, uid FROM storeid WHERE fid = %s", (id,))
    file_info = cursor.fetchone()
    conn.close()

    if file_info:
        db_filename, user_id = file_info
        if str(session.get('user_id')) == str(user_id):
            retrieved_string = crypt.getString(int(id))

            private_key = serialization.load_pem_private_key(
                session.get('private_key'),
                password=None,
                backend=default_backend()
            )

            try:
                decrypted_ipfs_hash = crypt.decrypt_with_private_key(private_key, base64.b64decode(retrieved_string)).decode('utf-8')

                file_content = crypt.ExtractPdfData(decrypted_ipfs_hash)

                pdf_file = BytesIO(file_content)

                response = make_response(send_file(pdf_file, mimetype='application/pdf'))
                response.headers['Content-Disposition'] = f'attachment; filename={filename}'

                return response
            except ValueError as e:
                return f'Decryption error: {e}', 500
        else:
            return 'Unauthorized', 401
    else:
        return 'File not found', 404

def pdf_to_text(pdf_path):
    try:
        poppler_path = r"C:\\Program Files\\poppler-24.02.0\\Library\\bin"
        images = convert_from_path(pdf_path, poppler_path=poppler_path)
        text = ""
        for img in images:
            img_text = pytesseract.image_to_string(img)
            text += img_text + "\n"
        return text
    except RuntimeError as e:
        if "Unable to get page count" in str(e):
            raise RuntimeError("Poppler not found or inaccessible. Please ensure Poppler's bin folder is in your PATH or specify the poppler_path argument in convert_from_path.") from e
        else:
            raise e  

def docx_to_text(docx_path):
    doc = Document(docx_path)
    text = []
    for paragraph in doc.paragraphs:
        text.append(paragraph.text)
    return "\n".join(text)

def doc_to_text(doc_path):
    word = win32.Dispatch("Word.Application")
    word.Visible = False
    doc = word.Documents.Open(doc_path)
    text = doc.Range().Text
    doc.Close()
    word.Quit()
    return text

def extract_text(file_path):
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext == ".pdf":
        return pdf_to_text(file_path)
    elif file_ext == ".docx":
        return docx_to_text(file_path)
    elif file_ext == ".doc":
        return doc_to_text(file_path)
    else:
        raise ValueError("Unsupported file format: {}".format(file_ext))

def authenticate_client():
    ta_credential = AzureKeyCredential(TEXT_ANALYTICS_KEY)
    text_analytics_client = TextAnalyticsClient(
        endpoint=TEXT_ANALYTICS_ENDPOINT, 
        credential=ta_credential)
    return text_analytics_client

def sample_extractive_summarization(client, document):
    poller = client.begin_analyze_actions(
        document,
        actions=[
            ExtractiveSummaryAction(max_sentence_count=20)
        ],
    )

    document_results = poller.result()
    for result in document_results:
        extract_summary_result = result[0]  
        if extract_summary_result.is_error:
            print("...Is an error with code '{}' and message '{}'".format(
                extract_summary_result.code, extract_summary_result.message
            ))
        else:
            return " ".join([sentence.text for sentence in extract_summary_result.sentences])

def translate_text(text, from_lang='en', to_lang='ta'):
    path = '/translate'
    constructed_url = TRANSLATOR_ENDPOINT + path

    params = {
        'api-version': '3.0',
        'from': from_lang,
        'to': [to_lang]
    }

    headers = {
        'Ocp-Apim-Subscription-Key': TRANSLATOR_KEY,
        'Ocp-Apim-Subscription-Region': TRANSLATOR_LOCATION,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }

    body = [{'text': text}]

    request = requests.post(constructed_url, params=params, headers=headers, json=body)
    response = request.json()
    return response[0]['translations'][0]['text']

@app.route('/analyze/<id>', methods=['GET'])
def analyze(id):
    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT filename, uid FROM storeid WHERE fid = %s", (id,))
    file_info = cursor.fetchone()
    conn.close()

    if file_info:
        filename, user_id = file_info
        if str(session.get('user_id')) == str(user_id):
            folder = 'uploads'
            for the_file in os.listdir(folder):
                file_path = os.path.join(folder, the_file)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f'Failed to delete {file_path}. Reason: {e}')

            retrieved_string = crypt.getString(int(id))
            private_key = serialization.load_pem_private_key(session.get('private_key'), password=None, backend=default_backend())
            try:
                decrypted_ipfs_hash = crypt.decrypt_with_private_key(private_key, base64.b64decode(retrieved_string)).decode('utf-8')

                file_content = crypt.ExtractPdfData(decrypted_ipfs_hash)

                file_path = os.path.join(folder, filename)
                with open(file_path, 'wb') as f:
                    f.write(file_content)

                file_text = extract_text(file_path)
                print("Text extracted")
                client = authenticate_client()
                summarized_text = sample_extractive_summarization(client, [file_text])
                print("Text summarized")
                print(summarized_text)
                translated_text = translate_text(summarized_text)
                print("Text translated")
                print(translated_text)
                return render_template('result.html', original_text=file_text, summarized_text=summarized_text, translated_text=translated_text)
            except ValueError as e:
                return {'success': False, 'error': str(e)}, 500
        else:
            return {'success': False, 'error': 'Unauthorized'}, 401
    else:
        return {'success': False, 'error': 'File not found'}, 404
    

def validate_user1(username, password):
    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM lawyer WHERE username = %s AND password = %s", (username, password))
    lawyer_id = cursor.fetchone()
    if lawyer_id:
        cursor.execute("SELECT privatekey, publickey FROM encryptlawyer WHERE lid = %s", (lawyer_id[0],))
        keys = cursor.fetchone()
        if keys:
            private_key = serialization.load_pem_private_key(keys[0], password=None, backend=default_backend())
            public_key = serialization.load_pem_public_key(keys[1], backend=default_backend())
            session['private_key_lawyer'] = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
            session['public_key_lawyer'] = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode('utf-8')
        else:
            private_key, public_key = crypt.generate_key_pair()
            private_key_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            cursor.execute("INSERT INTO encryptlawyer (lid, privatekey, publickey) VALUES (%s, %s, %s)",
                           (lawyer_id[0], private_key_bytes, public_key_bytes))
            conn.commit()
            session['private_key_lawyer'] = private_key_bytes.decode('utf-8')
            session['public_key_lawyer'] = public_key_bytes.decode('utf-8')
    conn.close()
    return lawyer_id



@app.route('/lawyerLogin', methods=['GET', 'POST'])
def login1():
    session.clear()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        lawyer_id = validate_user1(username, password)
        if lawyer_id:
            session['lawyer_id'] = lawyer_id[0]
            return redirect('/upload_doc_lawyer1')
        else:
            login_message = "Invalid username or password"
            return render_template('loginLawyer.html', login_message=login_message)
    return render_template('loginLawyer.html')

@app.route('/upload_doc_lawyer1')
def upload_doc1():
    lawyer_id = session.get('lawyer_id')
    if not lawyer_id:
        return redirect('/login1')

    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT fid, filename FROM storeidlawyer WHERE lid = %s", (lawyer_id,))
    files = cursor.fetchall()
    conn.close()
    return render_template('UploadDoc_lawyer.html', lawyer_id=lawyer_id, files=files)

@app.route('/create_account_lawyer', methods=['GET', 'POST'])
def create_account1():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']
        private_key, public_key = crypt.generate_key_pair()
        
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        try:
            conn = connect_to_mysql()
            cursor = conn.cursor()
            sql = "INSERT INTO lawyer (name, username, password) VALUES (%s, %s, %s)"
            val = (name, username, password)
            cursor.execute(sql, val)
            
            lawyer_id = cursor.lastrowid
            
            sql = "INSERT INTO encryptlawyer (lid, privatekey, publickey) VALUES (%s, %s, %s)"
            val = (lawyer_id, private_key_bytes, public_key_bytes)
            cursor.execute(sql, val)
            
            conn.commit()
            conn.close()
            
            return redirect('/')
        except mysql.connector.Error as e:
            print("Error:", e)
            return "An error occurred while processing your request."
        
    return render_template('create_account_lawyer.html')

@app.route('/upload1', methods=['POST'])
def upload1():
    lawyer_id = session.get('lawyer_id')
    if not lawyer_id:
        return redirect('/login1')

    if 'file' not in request.files or request.files['file'].filename == '':
        return 'No selected file'

    file = request.files['file']
    filepath = os.path.join('uploads', file.filename)
    file.save(filepath)

    ipfs_hash = crypt.upload_pdf(filepath)
    os.remove(filepath)

    public_key = serialization.load_pem_public_key(session.get('public_key_lawyer').encode(), backend=default_backend())
    encrypted_ipfs_hash = crypt.encrypt_with_public_key(public_key, ipfs_hash)
    encrypted_ipfs_hash_str = base64.b64encode(encrypted_ipfs_hash).decode("utf-8")
    crypt.store_string(encrypted_ipfs_hash_str)

    file_id = crypt.getId()
    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO storeidlawyer (lid, fid, filename) VALUES (%s, %s, %s)",
                   (lawyer_id, file_id, file.filename))
    conn.commit()
    conn.close()

    return redirect('/upload_doc_lawyer1')

@app.route('/retrieve1/<id>', methods=['GET'])
def retrieve1(id):
    filename = request.args.get('filename')

    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT filename, lid FROM storeidlawyer WHERE fid = %s", (id,))
    file_info = cursor.fetchone()
    conn.close()

    if file_info:
        db_filename, lawyer_id = file_info
        if str(session.get('lawyer_id')) == str(lawyer_id):
            retrieved_string = crypt.getString(int(id))

            private_key = serialization.load_pem_private_key(
                session.get('private_key_lawyer').encode(),
                password=None,
                backend=default_backend()
            )

            try:
                decrypted_ipfs_hash = crypt.decrypt_with_private_key(private_key, base64.b64decode(retrieved_string)).decode('utf-8')

                file_content = crypt.ExtractPdfData(decrypted_ipfs_hash)

                pdf_file = BytesIO(file_content)

                response = make_response(send_file(pdf_file, mimetype='application/pdf'))
                response.headers['Content-Disposition'] = f'attachment; filename={filename}'

                return response
            except ValueError as e:
                return f'Decryption error: {e}', 500
        else:
            return 'Unauthorized', 401
    else:
        return 'File not found', 404

@app.route('/fetch_files1', methods=['POST'])
def fetch_files1():
    client_id = request.form.get('client_id')
    lawyer_id = session.get('lawyer_id')

    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM lawuser_rel WHERE uid = %s AND lid = %s", (client_id, lawyer_id))
    if not cursor.fetchone():
        conn.close()
        return 'Unauthorized', 401

    cursor.execute("SELECT fid, filename FROM storeid WHERE uid = %s", (client_id,))
    files = cursor.fetchall()
    conn.close()

    files_data = ';'.join([f'{fid},{filename}' for fid, filename in files])
    return files_data



def validate_user2(username, password):
    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM admin WHERE username = %s AND password = %s", (username, password))
    ad_id = cursor.fetchone()
    if ad_id:
        session['ad_id'] = ad_id[0]
        cursor.execute("SELECT privatekey, publickey FROM encryptadmin WHERE adid = %s", (ad_id[0],))
        keys = cursor.fetchone()
        if keys:
            private_key = serialization.load_pem_private_key(keys[0], password=None, backend=default_backend())
            public_key = serialization.load_pem_public_key(keys[1], backend=default_backend())
            session['private_key_admin'] = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
            session['public_key_admin'] = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode('utf-8')
        else:
            private_key, public_key = crypt.generate_key_pair()
            private_key_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            cursor.execute("INSERT INTO encryptadmin(adid, privatekey, publickey) VALUES (%s, %s, %s)",
                           (ad_id[0], private_key_bytes.decode('utf-8'), public_key_bytes.decode('utf-8')))
            conn.commit()
            session['private_key_admin'] = private_key_bytes.decode('utf-8')
            session['public_key_admin'] = public_key_bytes.decode('utf-8')
    conn.close()
    return ad_id

@app.route('/judge', methods=['GET', 'POST'])
def login2():
    session.clear()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        ad_id = validate_user2(username, password)
        if ad_id:
            return redirect('/UploadDoc_law_admin2')
        else:
            login_message = "Invalid username or password"
            print("Cannot login to admin")
            return render_template('loginAdmin.html', login_message=login_message)
  
    return render_template('loginAdmin.html')

@app.route('/create_account_admin', methods=['GET', 'POST'])
def create_account2():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']
        crypt = Crypt()
        private_key, public_key = crypt.generate_key_pair()
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        conn = connect_to_mysql()
        cursor = conn.cursor()
        sql = "INSERT INTO admin (name, username, password) VALUES (%s, %s, %s)"
        val = (name, username, password)
        cursor.execute(sql, val)
        id = cursor.lastrowid
        sql = "INSERT INTO encryptadmin (adid, privatekey, publickey) VALUES (%s, %s, %s)"
        val = (id, private_key_bytes, public_key_bytes)
        cursor.execute(sql, val)
        
        conn.commit()
        conn.close()
        
        return redirect('/2')
    return render_template('create_account_admin.html')

@app.route('/UploadDoc_law_admin2')
def upload_doc2():
    ad_id = session.get('ad_id')
    if ad_id:
        conn = connect_to_mysql()
        cursor = conn.cursor()
        cursor.execute("SELECT fid, filename FROM storeidad WHERE adid = %s", (ad_id,))
        files = cursor.fetchall()
        conn.close()
        return render_template('UploadDoc_law_admin.html', aud_id=ad_id, files=files)
    else:
        return redirect('/2')

@app.route('/upload2', methods=['POST'])
def upload2():
    ad_id = session.get('ad_id')
    if not ad_id:
        return redirect('/2')
    
    if 'file' not in request.files:
        return 'No file part'
    file = request.files['file']
    if file.filename == '':
        return 'No selected file'
    
    if file:
        file.save(os.path.join('uploads', file.filename))
        
        ipfs_hash = crypt.upload_pdf(os.path.join('uploads', file.filename))
        os.remove(os.path.join('uploads', file.filename))
        
        public_key = serialization.load_pem_public_key(session.get('public_key_admin').encode(), backend=default_backend())
        encrypted_ipfs_hash = crypt.encrypt_with_public_key(public_key, ipfs_hash)
        
        encrypted_ipfs_hash_str = base64.b64encode(encrypted_ipfs_hash).decode("utf-8")
        crypt.store_string(encrypted_ipfs_hash_str)
        
        id = crypt.getId()
        conn = connect_to_mysql()
        cursor = conn.cursor()
        
        sql = "INSERT INTO storeidad (adid, fid, filename) VALUES (%s, %s, %s)"
        val = (ad_id, id, file.filename)
        cursor.execute(sql, val)
        
        conn.commit()
        conn.close()
        
        return redirect('/UploadDoc_law_admin2')

@app.route('/retrieve2/<id>', methods=['GET'])
def retrieve2(id):
    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT filename, adid FROM storeidad WHERE fid = %s", (id,))
    file_info = cursor.fetchone()
    conn.close()
    
    if file_info:
        filename, ad_id = file_info
        if str(session.get('ad_id')) == str(ad_id):
            retrieved_string = crypt.getString(int(id))
            private_key = serialization.load_pem_private_key(
                session.get('private_key_admin').encode(),
                password=None,
                backend=default_backend()
            )
            try:
                decrypted_ipfs_hash = crypt.decrypt_with_private_key(
                    private_key,
                    base64.b64decode(retrieved_string)
                ).decode('utf-8')
                
                file_content = crypt.ExtractPdfData(decrypted_ipfs_hash)
                
                content_type = get_mime_type(filename)
                return send_file(BytesIO(file_content), mimetype=content_type, download_name=filename)
            except ValueError as e:
                return f'Decryption error: {e}', 500
        else:
            return 'Unauthorized', 401
    else:
        return 'File not found', 404

@app.route('/update2', methods=['POST'])
def update2():
    aud = request.form['aud']
    lid = request.form['lid']
    uid = request.form['uid']
    print("update entered")
    update_lawuser_rel(aud, lid, uid)
    return redirect('/UploadDoc_law_admin2')

@app.route('/delete2', methods=['POST'])
def delete2():
    aud = request.form['aud']
    id = request.form['id']
    delete_data(aud, id)
    return redirect('/UploadDoc_law_admin2')

def update_lawuser_rel(aud, lid, uid):
    try:
        conn = connect_to_mysql()
        cursor = conn.cursor()
        
        if aud:
            print(aud,' Updating')
            cursor.execute("update lawuser_rel set lid = %s where uid = %s", (lid, uid))
        else:
            cursor.execute("update lawuser_rel set uid = %s where lid = %s", (lid, lid))
            conn.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        cursor.close()
        conn.close()

def delete_data(aud, id):
    try:
        conn = connect_to_mysql()
        cursor = conn.cursor()
        
        if aud:
            cursor.execute("delete from lawyer where id = %s", (id,))
            cursor.execute("delete from lawuser_rel where lid = %s", (id,))
        else:
            cursor.execute("delete from user where id = %s", (id,))
            cursor.execute("delete from lawuser_rel where uid = %s", (id,))
        
        conn.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        cursor.close()
        conn.close()

def get_mime_type(filename):
    mime_types = {
        '.pdf': 'application/pdf',
        '.csv': 'text/csv',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.txt': 'text/plain',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.tif': 'image/tiff',
        '.tiff': 'image/tiff',
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.ogg': 'audio/ogg',
        '.mp4': 'video/mp4',
        '.avi': 'video/x-msvideo',
        '.mkv': 'video/x-matroska',
        '.mov': 'video/quicktime',
        '.zip': 'application/zip',
        '.rar': 'application/x-rar-compressed',
        '.tar': 'application/x-tar',
        '.gz': 'application/gzip',
        '.7z': 'application/x-7z-compressed'
    }

    ext = os.path.splitext(filename)[1].lower()

    return mime_types.get(ext, 'application/octet-stream')

def validate_user3(username, password):
    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM user WHERE username = %s AND password = %s", (username, password))
    user_id = cursor.fetchone()
    if user_id:
        cursor.execute("SELECT privatekey, publickey FROM encrypt WHERE uid = %s", (user_id[0],))
        keys = cursor.fetchone()
        if keys:
            private_key = serialization.load_pem_private_key(keys[0], password=None, backend=default_backend())
            public_key = serialization.load_pem_public_key(keys[1], backend=default_backend())
            session['private_key3'] = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            session['public_key3'] = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        else:
            private_key, public_key = crypt.generate_key_pair()
            private_key_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            cursor.execute("INSERT INTO encrypt (uid, privatekey, publickey) VALUES (%s, %s, %s)",
                           (user_id[0], private_key_bytes, public_key_bytes))
            conn.commit()
            session['private_key3'] = private_key_bytes
            session['public_key3'] = public_key_bytes
    conn.close()
    return user_id

@app.route('/userFin', methods=['GET', 'POST'])
def login3():
    session.clear()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_id = validate_user3(username, password)
        if user_id:
            session['user_id3'] = user_id[0]
            return redirect('/UploadDoc3')
        else:
            login_message = "Invalid username or password"
            return render_template('login.html', login_message=login_message)
    return render_template('login.html')

@app.route('/create_account_fuser', methods=['GET', 'POST'])
def create_account3():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']
        auditorid = request.form['auditorid']
        
        crypt = Crypt()
        private_key, public_key = crypt.generate_key_pair()
        
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        conn = connect_to_mysql()
        cursor = conn.cursor()
        sql = "INSERT INTO user (name, username, password) VALUES (%s, %s, %s)"
        val = (name, username, password)
        cursor.execute(sql, val)
        
        user_id = cursor.lastrowid
        
        sql = "INSERT INTO aurel (uid,aid) VALUES (%s, %s)"
        val = (user_id, auditorid)
        cursor.execute(sql, val)
        
        sql = "INSERT INTO encrypt (uid, privatekey, publickey) VALUES (%s, %s, %s)"
        val = (user_id, private_key_bytes, public_key_bytes)
        cursor.execute(sql, val)
        
        conn.commit()
        conn.close()
        
        return redirect('/3')
    return render_template('create_account.html')

@app.route('/UploadDoc3')
def upload_doc3():
    user_id = session.get('user_id3')
    if user_id:
        conn = connect_to_mysql()
        cursor = conn.cursor()
        cursor.execute("SELECT fid, filename FROM storeid WHERE uid = %s", (user_id,))
        files = cursor.fetchall()
        conn.close()
        return render_template('UploadDoc.html', user_id=user_id, files=files)
    else:
        return redirect('/3')

@app.route('/upload3', methods=['POST'])
def upload3():
    user_id = session.get('user_id3')
    if not user_id:
        return redirect('/3')

    if 'file' not in request.files:
        return 'No file part'
    file = request.files['file']
    if file.filename == '':
        return 'No selected file'

    if file:
        file.save('uploads/' + file.filename)

        ipfs_hash = crypt.upload_pdf(f"uploads/{file.filename}")
        os.remove(f"uploads/{file.filename}")

        public_key = serialization.load_pem_public_key(session.get('public_key3'), backend=default_backend())
        encrypted_ipfs_hash = crypt.encrypt_with_public_key(public_key, ipfs_hash)

        encrypted_ipfs_hash_str = base64.b64encode(encrypted_ipfs_hash).decode("utf-8")
        crypt.store_string(encrypted_ipfs_hash_str)

        id = crypt.getId()
        conn = connect_to_mysql()
        cursor = conn.cursor()

        sql = "INSERT INTO storeid (uid, fid, filename) VALUES (%s, %s, %s)"
        val = (user_id, id, file.filename)
        cursor.execute(sql, val)

        conn.commit()
        conn.close()

        return redirect('/UploadDoc3')

@app.route('/retrieve3/<id>', methods=['GET'])
def retrieve3(id):
    filename = request.args.get('filename')
    
    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT filename, uid FROM storeid WHERE fid = %s", (id,))
    file_info = cursor.fetchone()
    conn.close()

    if file_info:
        db_filename, user_id = file_info
        if str(session.get('user_id3')) == str(user_id):
            retrieved_string = crypt.getString(int(id))

            private_key = serialization.load_pem_private_key(
                session.get('private_key3'),
                password=None,
                backend=default_backend()
            )

            try:
                decrypted_ipfs_hash = crypt.decrypt_with_private_key(private_key, base64.b64decode(retrieved_string)).decode('utf-8')

                file_content = crypt.ExtractPdfData(decrypted_ipfs_hash)

                pdf_file = BytesIO(file_content)

                response = make_response(send_file(pdf_file, mimetype='application/pdf'))
                response.headers['Content-Disposition'] = f'attachment; filename={filename}'

                return response
            except ValueError as e:
                return f'Decryption error: {e}', 500
        else:
            return 'Unauthorized', 401
    else:
        return 'File not found', 404
      
def clear_uploads_folder():
    folder = 'uploads'
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')
      
@app.route('/analyze2/<id>', methods=['GET'])
def analyze2(id):
    filename = request.args.get('filename')
    
    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT filename, uid FROM storeid WHERE fid = %s", (id,))
    file_info = cursor.fetchone()
    conn.close()

    if file_info:
        db_filename, user_id = file_info
        print(user_id)
        print(session.get('user_id'))
        if str(session.get('user_id3')) == str(user_id):
            retrieved_string = crypt.getString(int(id))

            private_key = serialization.load_pem_private_key(
                session.get('private_key3'),
                password=None,
                backend=default_backend()
            )

            try:
                decrypted_ipfs_hash = crypt.decrypt_with_private_key(private_key, base64.b64decode(retrieved_string)).decode('utf-8')

                file_content = crypt.ExtractPdfData(decrypted_ipfs_hash)
                
                clear_uploads_folder()
                file_path = f'uploads/{filename}'
                with open(file_path, 'wb') as file:
                    file.write(file_content)

                global df
                df = pd.read_csv(file_path)

                return render_template('index.html', result="File analyzed and stored successfully", filename=filename)

            except ValueError as e:
                return f'Decryption error: {e}', 500
        else:
            return 'Unauthorized', 401
    else:
        return 'File not found', 404


df = pd.DataFrame()

def calculate_statistic(df, column, stat, start_idx, end_idx):
    if column in df.columns and 0 <= start_idx < len(df) and 0 <= end_idx < len(df) and start_idx <= end_idx:
        selected_data = df[column].iloc[start_idx:end_idx + 1]
        if stat == 'mean':
            return selected_data.mean()
        elif stat == 'sum':
            return selected_data.sum()
        elif stat == 'median':
            return selected_data.median()
        elif stat == 'mode':
            mode_result = stats.mode(selected_data)
            return mode_result.mode[0] if isinstance(mode_result.mode, np.ndarray) and len(mode_result.mode) > 0 else np.nan
    return None

@app.route('/cal', methods=['GET', 'POST'])
def statistics():
    global df
    result = None
    if request.method == 'POST':
        column = request.form['column']
        try:
            start_idx = int(request.form['start_idx'])
            end_idx = int(request.form['end_idx'])
            stat = request.form['stat']
            if column not in df.columns:
                result = "Invalid column name."
            elif not (0 <= start_idx < len(df)) or not (0 <= end_idx < len(df)) or start_idx > end_idx:
                result = "Invalid index range."
            else:
                result = calculate_statistic(df, column, stat, start_idx, end_idx)
                result = f"{stat.capitalize()} of column {column} from index {start_idx} to {end_idx}: {result}"
        except ValueError:
            result = "Invalid input. Please enter numeric values for indices."
    else:
        uploads = 'uploads'
        file_list = os.listdir(uploads)
        if file_list:
            file_path = os.path.join(uploads, file_list[0])
            df = pd.read_csv(file_path)
            result = "Pre-analyzed file loaded successfully. You can now perform operations."
    return render_template('index.html', result=result)

@app.route('/predict', methods=['POST'])
def predict():
    global df

    try:
        start_index = int(request.form['start_index'])
        end_index = int(request.form['end_index'])
        year_input = int(request.form['year_input'])
        
        indep = request.form['indep'].lower()
        dep = request.form['dep'].lower()
    except ValueError:
        return jsonify({'error': 'Invalid input. Please enter numeric values for indices and year.'})

    df.columns = map(str.lower, df.columns)

    if indep not in df.columns or dep not in df.columns:
        return jsonify({'error': f'Invalid column names. Ensure "{indep}" and "{dep}" exist in the dataframe.'})

    if start_index < 0 or end_index >= len(df) or start_index > end_index:
        return jsonify({'error': 'Invalid index range. Ensure start_index and end_index are within valid range and start_index <= end_index.'})

    df_range = df.iloc[start_index:end_index + 1]

    X = df_range[[indep]].values
    y = df_range[dep].values

    model = RandomForestRegressor(n_estimators=200, random_state=42)
    model.fit(X, y)

    predicted_profit = model.predict(np.array([[year_input]]))[0]
    return jsonify({'predicted_profit': predicted_profit})

@app.route('/display', methods=['POST'])
def display():
    global df

    try:
        start_index = int(request.form['start_index'])
        end_index = int(request.form['end_index'])
        year_input = int(request.form['year_input'])
        
        indep = request.form['indep'].lower()
        dep = request.form['dep'].lower()
    except ValueError:
        return jsonify({'error': 'Invalid input. Please enter numeric values for indices and year.'})

    df.columns = map(str.lower, df.columns)

    if indep not in df.columns or dep not in df.columns:
        return jsonify({'error': f'Invalid column names. Ensure "{indep}" and "{dep}" exist in the dataframe.'})

    if start_index < 0 or end_index >= len(df) or start_index > end_index:
        return jsonify({'error': 'Invalid index range. Ensure start_index and end_index are within valid range and start_index <= end_index.'})

    df_range = df.iloc[start_index:end_index + 1]

    X = df_range[[indep]].values
    y = df_range[dep].values

    model = RandomForestRegressor(n_estimators=200, random_state=42)
    model.fit(X, y)

    
    pred_profit = model.predict(np.array([[year_input]]))[0]
    
    plt.figure(figsize=(6, 6))
    plt.scatter(X, y, color='blue', label='Actual data')
    plt.plot(year_input, pred_profit, color='red', linestyle='dashed', marker='o', label='Predicted profit')
    plt.xlabel('Year')
    plt.ylabel('Profit')
    plt.title('Profit Prediction')
    plt.legend()
    plt.grid(True)

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()

    return jsonify({'plot_url': plot_url})
      

def validate_user4(username, password):
    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM admin WHERE username = %s AND password = %s", (username, password))
    ad_id = cursor.fetchone()
    if ad_id:
        session['ad_id'] = ad_id[0]
        cursor.execute("SELECT privatekey, publickey FROM encryptadmin WHERE adid = %s", (ad_id[0],))
        keys = cursor.fetchone()
        if keys:
            private_key = serialization.load_pem_private_key(keys[0], password=None, backend=default_backend())
            public_key = serialization.load_pem_public_key(keys[1], backend=default_backend())
            session['private_key'] = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            session['public_key'] = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        else:
            private_key, public_key = crypt.generate_key_pair()
            private_key_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            cursor.execute("INSERT INTO encryptadmin(adid, privatekey, publickey) VALUES (%s, %s, %s)",
                           (ad_id[0], private_key_bytes, public_key_bytes))
            conn.commit()
            session['private_key'] = private_key_bytes
            session['public_key'] = public_key_bytes
    conn.close()
    return ad_id

@app.route('/AdminFin', methods=['GET', 'POST'])
def login4():
    session.clear()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        ad_id = validate_user4(username, password)
        if ad_id:
            return redirect('/UploadDoc_fin_admin4')
        else:
            login_message = "Invalid username or password"
            print("Can not login to admin")
            return render_template('loginAdminFin.html', login_message=login_message)
  
    return render_template('loginAdminFin.html')

@app.route('/create_account_fadmin', methods=['GET', 'POST'])
def create_account4():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']
        
        crypt = Crypt()
        private_key, public_key = crypt.generate_key_pair()
        
        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        conn = connect_to_mysql()
        cursor = conn.cursor()
        sql = "INSERT INTO admin (name, username, password) VALUES (%s, %s, %s)"
        val = (name, username, password)
        cursor.execute(sql, val)
        
        id = cursor.lastrowid
        
        
        sql = "INSERT INTO encryptadmin (adid, privatekey, publickey) VALUES (%s, %s, %s)"
        val = (id, private_key_bytes, public_key_bytes)
        cursor.execute(sql, val)
        
        conn.commit()
        conn.close()
        
        return redirect('/')
    return render_template('create_account_admin.html')

@app.route('/UploadDoc_fin_admin4')
def upload_doc4():
    ad_id = session.get('ad_id')
    if ad_id:
        conn = connect_to_mysql()
        cursor = conn.cursor()
        cursor.execute("SELECT fid, filename FROM storeidad WHERE adid = %s", (ad_id,))
        files = cursor.fetchall()
        conn.close()
        return render_template('UploadDoc_fin_admin.html', aud_id=ad_id, files=files)
    else:
        return redirect('/')

@app.route('/upload4', methods=['POST'])
def upload4():
    ad_id = session.get('ad_id')
    if not ad_id:
        return redirect('/')
    
    if 'file' not in request.files:
        return 'No file part'
    file = request.files['file']
    if file.filename == '':
        return 'No selected file'
    
    if file:
        file.save(os.path.join('uploads', file.filename))
        
        ipfs_hash = crypt.upload_pdf(os.path.join('uploads', file.filename))
        os.remove(os.path.join('uploads', file.filename))
        
        public_key = serialization.load_pem_public_key(session.get('public_key'), backend=default_backend())
        encrypted_ipfs_hash = crypt.encrypt_with_public_key(public_key, ipfs_hash)
        
        encrypted_ipfs_hash_str = base64.b64encode(encrypted_ipfs_hash).decode("utf-8")
        crypt.store_string(encrypted_ipfs_hash_str)
        
        id = crypt.getId()
        conn = connect_to_mysql()
        cursor = conn.cursor()
        
        sql = "INSERT INTO storeidad (adid, fid, filename) VALUES (%s, %s, %s)"
        val = (ad_id, id, file.filename)
        cursor.execute(sql, val)
        
        conn.commit()
        conn.close()
        
        return redirect('/UploadDoc_fin_admin4')

@app.route('/retrieve4/<id>', methods=['GET'])
def retrieve4(id):
    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT filename, adid FROM storeidad WHERE fid = %s", (id,))
    file_info = cursor.fetchone()
    conn.close()
    
    if file_info:
        filename, ad_id = file_info
        if str(session.get('ad_id')) == str(ad_id):
            retrieved_string = crypt.getString(int(id))
            print(id)

            private_key = serialization.load_pem_private_key(
                session.get('private_key'),
                password=None,
                backend=default_backend()
            )

            try:
                decrypted_ipfs_hash = crypt.decrypt_with_private_key(private_key, base64.b64decode(retrieved_string)).decode('utf-8')
                print(decrypted_ipfs_hash)

                file_content = crypt.ExtractPdfData(decrypted_ipfs_hash)

                pdf_file = BytesIO(file_content)

                response = make_response(send_file(pdf_file, mimetype='application/pdf'))
                response.headers['Content-Disposition'] = f'attachment; filename={filename}'

                return response
            except ValueError as e:
                return f'Decryption error: {e}', 500
        else:
            return 'Unauthorized', 401
    else:
        return 'File not found', 404

@app.route('/update4', methods=['POST'])
def update4():
    aud = request.form['aud']
    aid = request.form['aid']
    uid = request.form['uid']
    update_aurel4(aud, aid, uid)
    return redirect('/UploadDoc_fin_admin4')

@app.route('/delete4', methods=['POST'])
def delete4():
    aud = request.form['aud']
    id = request.form['id']
    delete_data4(aud, id)
    return redirect('/UploadDoc_fin_admin4')

def update_aurel4(aud, aid, uid):
    try:
        conn = connect_to_mysql()
        cursor = conn.cursor()
        
        if aud:
            cursor.execute("update aurel set aid = %s where uid = %s", (aid, uid))
        else:
            cursor.execute("update aurel set uid = %s where aid = %s", (uid, aid))
        
        conn.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        cursor.close()
        conn.close()

def delete_data4(aud, id):
    try:
        conn = connect_to_mysql()
        cursor = conn.cursor()
        
        if aud:
            #print("Deleting")
            cursor.execute("delete from adet where id = %s", (id,))
            cursor.execute("delete from aurel where aid = %s",(id,))
        else:
            #print("Deleting")
            cursor.execute("delete from user where id = %s", (id,))
            cursor.execute("delete from aurel where uid = %s",(id,))
        
        conn.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        cursor.close()
        conn.close()
   

def validate_user5(username, password):
    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM adet WHERE username = %s AND password = %s", (username, password))
    aud_id = cursor.fetchone()
    if aud_id:
        cursor.execute("SELECT privatekey, publickey FROM encryptaud WHERE aid = %s", (aud_id[0],))
        keys = cursor.fetchone()
        if keys:
            private_key = serialization.load_pem_private_key(keys[0], password=None, backend=default_backend())
            public_key = serialization.load_pem_public_key(keys[1], backend=default_backend())
            session['private_key_aud'] = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            session['public_key_aud'] = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        else:
            private_key, public_key = crypt.generate_key_pair()
            private_key_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            cursor.execute("INSERT INTO encryptaud (aid, privatekey, publickey) VALUES (%s, %s, %s)",
                           (aud_id[0], private_key_bytes, public_key_bytes))
            conn.commit()
            session['private_key_aud'] = private_key_bytes
            session['public_key_aud'] = public_key_bytes
    conn.close()
    return aud_id

@app.route('/Auditor', methods=['GET', 'POST'])
def login5():
    session.clear()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        aud_id = validate_user5(username, password)
        if aud_id:
            session['aud_id'] = aud_id[0]
            return redirect('/UploadDoc_auditor5')
        else:
            login_message = "Invalid username or password"
            return render_template('loginAuditor.html', login_message=login_message)
    return render_template('loginAuditor.html')

@app.route('/create_account_auditor', methods=['GET', 'POST'])
def create_account5():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']

        private_key, public_key = generate_key_pair()

        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        try:
            conn = connect_to_mysql()
            cursor = conn.cursor()
            sql = "INSERT INTO adet (name, username, password) VALUES (%s, %s, %s)"
            val = (name, username, password)
            cursor.execute(sql, val)
            aud_id = cursor.lastrowid
            sql = "INSERT INTO encryptaud (aid, privatekey, publickey) VALUES (%s, %s, %s)"
            val = (aud_id, private_key_bytes, public_key_bytes)
            cursor.execute(sql, val)
            
            conn.commit()
            conn.close()
            
            return redirect('/login5')
        except mysql.connector.Error as e:
            print("Error:", e)
            return "An error occurred while processing your request."
        
    return render_template('create_account_auditor.html')

@app.route('/UploadDoc_auditor5')
def upload_doc5():
    aud_id = session.get('aud_id')
    if aud_id:
        conn = connect_to_mysql()
        cursor = conn.cursor()
        cursor.execute("SELECT fid, filename FROM storeidaud WHERE aid = %s", (aud_id,))
        files = cursor.fetchall()
        conn.close()
        return render_template('UploadDoc_auditor.html', aud_id=aud_id, files=files)
    else:
        return redirect('/login5')

@app.route('/upload5', methods=['POST'])
def upload5():
    aud_id = session.get('aud_id')
    if not aud_id:
        return redirect('/login5')
    
    if 'file' not in request.files:
        return 'No file part'
    file = request.files['file']
    if file.filename == '':
        return 'No selected file'
    
    if file:
        file.save('uploads/' + file.filename)
        
        ipfs_hash = crypt.upload_pdf(f"uploads/{file.filename}")
        os.remove(f"uploads/{file.filename}")
        
        public_key = serialization.load_pem_public_key(session.get('public_key_aud'), backend=default_backend())
        encrypted_ipfs_hash = crypt.encrypt_with_public_key(public_key, ipfs_hash)
        
        encrypted_ipfs_hash_str = base64.b64encode(encrypted_ipfs_hash).decode("utf-8")
        crypt.store_string(encrypted_ipfs_hash_str)
        
        id = crypt.getId()
        conn = connect_to_mysql()
        cursor = conn.cursor()
        
        sql = "INSERT INTO storeidaud (aid, fid, filename) VALUES (%s, %s, %s)"
        val = (aud_id, id, file.filename)
        cursor.execute(sql, val)
        
        conn.commit()
        conn.close()
        
        return redirect('/UploadDoc_auditor5')

@app.route('/retrieve5/<id>', methods=['GET'])
def retrieve5(id):
    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT filename, aid FROM storeidaud WHERE fid = %s", (id,))
    file_info = cursor.fetchone()
    conn.close()
    
    if file_info:
        filename, aud_id = file_info
        if str(session.get('aud_id')) == str(aud_id):
            retrieved_string = crypt.getString(int(id))

            private_key = serialization.load_pem_private_key(
                session.get('private_key_aud'),
                password=None,
                backend=default_backend()
            )

            try:
                decrypted_ipfs_hash = crypt.decrypt_with_private_key(private_key, base64.b64decode(retrieved_string)).decode('utf-8')

                file_content = crypt.ExtractPdfData(decrypted_ipfs_hash)

                pdf_file = BytesIO(file_content)

                response = make_response(send_file(pdf_file, mimetype='application/pdf'))
                response.headers['Content-Disposition'] = f'attachment; filename={filename}'

                return response
            except ValueError as e:
                return f'Decryption error: {e}', 500
        else:
            return 'Unauthorized', 401
    else:
        return 'File not found', 404

@app.route('/fetch_files5', methods=['POST'])
def fetch_files5():
    client_id = request.form.get('client_id')
    aud_id = session.get('aud_id')
    print(client_id, aud_id, 'client and auditor')
    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM aurel WHERE uid = %s AND aid = %s", (client_id, aud_id))
    id = cursor.fetchone()
    conn.close()
    print('id :', id)
    if id:
        conn = connect_to_mysql()
        cursor = conn.cursor()
        cursor.execute("SELECT fid, filename FROM storeid WHERE uid = %s", (client_id,))
        files = cursor.fetchall()
        conn.close()

        files_data = ';'.join([f'{fid},{filename}' for fid, filename in files])
        print("files data :", files_data)
        return files_data
    else:
        return 'Unauthorized', 401
      
      
@app.route('/retrieve6/<id>', methods=['GET'])
def retrieve6(id):
    conn = connect_to_mysql()
    cursor = conn.cursor()
    
    cursor.execute("SELECT filename, uid FROM storeid WHERE fid = %s", (id,))
    file_info = cursor.fetchone()
    conn.close()
    
    if file_info:
        filename, uid = file_info
        
        conn = connect_to_mysql()
        cursor = conn.cursor()
        cursor.execute("SELECT privatekey, publickey FROM encrypt WHERE uid = %s", (uid,))
        keys = cursor.fetchone()
        conn.close()

        if keys:
            private_key = serialization.load_pem_private_key(keys[0], password=None, backend=default_backend())
            retrieved_string = crypt.getString(int(id))

            try:
                decrypted_ipfs_hash = crypt.decrypt_with_private_key(private_key, base64.b64decode(retrieved_string)).decode('utf-8')

                file_content = crypt.ExtractPdfData(decrypted_ipfs_hash)

                pdf_file = BytesIO(file_content)

                response = make_response(send_file(pdf_file, mimetype='application/pdf'))
                response.headers['Content-Disposition'] = f'attachment; filename={filename}'

                return response
            except ValueError as e:
                return f'Decryption error: {e}', 500
        else:
            return 'Encryption keys not found', 404
    else:
        return 'File not found', 404
      
def validate_user9(username, password):
    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM user WHERE username = %s AND password = %s", (username, password))
    user_id = cursor.fetchone()
    if user_id:
        cursor.execute("SELECT privatekey, publickey FROM encrypt WHERE uid = %s", (user_id[0],))
        keys = cursor.fetchone()
        if keys:
            private_key = serialization.load_pem_private_key(keys[0], password=None, backend=default_backend())
            public_key = serialization.load_pem_public_key(keys[1], backend=default_backend())
            session['private_key'] = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            session['public_key'] = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        else:
            crypt = Crypt()
            private_key, public_key = crypt.generate_key_pair()
            private_key_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            cursor.execute("INSERT INTO encrypt (uid, privatekey, publickey) VALUES (%s, %s, %s)",
                           (user_id[0], private_key_bytes, public_key_bytes))
            conn.commit()
            session['private_key'] = private_key_bytes
            session['public_key'] = public_key_bytes
    conn.close()
    return user_id

@app.route('/willUpd', methods=['GET', 'POST'])
def login9():
    session.clear()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_id = validate_user9(username, password)
        if user_id:
            session['user_id'] = user_id[0]
            return redirect('/upload_doc9')
        else:
            login_message = "Invalid username or password"
            return render_template('loginLawUser.html', login_message=login_message)
    return render_template('loginLawUser.html')

@app.route('/create_account_luser', methods=['GET', 'POST'])
def create_account9():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']
        lawyerid = request.form['lawyerid']

        crypt = Crypt()
        private_key, public_key = crypt.generate_key_pair()

        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        conn = connect_to_mysql()
        cursor = conn.cursor()
        sql = "INSERT INTO user (name, username, password) VALUES (%s, %s, %s)"
        val = (name, username, password)
        cursor.execute(sql, val)
        user_id = cursor.lastrowid

        sql = "INSERT INTO lawuser_rel (uid, lid) VALUES (%s, %s)"
        val = (user_id, lawyerid)
        cursor.execute(sql, val)

        sql = "INSERT INTO encrypt (uid, privatekey, publickey) VALUES (%s, %s, %s)"
        val = (user_id, private_key_bytes, public_key_bytes)
        cursor.execute(sql, val)

        conn.commit()
        conn.close()

        return redirect('/')
    return render_template('create_account_luser.html')

@app.route('/upload_doc9')
def upload_doc9():
    user_id = session.get('user_id')
    if user_id:
        conn = connect_to_mysql()
        cursor = conn.cursor()
        cursor.execute("SELECT fid, will_file FROM `will` WHERE uid = %s", (user_id,))
        files = cursor.fetchall()
        conn.close()
        return render_template('willUpdate.html', user_id=user_id, files=files)
    else:
        return redirect('/')

@app.route('/upload9', methods=['POST'])
def upload9():
    user_id = session.get('user_id')
    if not user_id:
        return redirect('/')

    if 'file' not in request.files:
        return 'No file part'
    file = request.files['file']
    if file.filename == '':
        return 'No selected file'

    if file:
        file.save('uploads/' + file.filename)

        ipfs_hash = crypt.upload_pdf(f"uploads/{file.filename}")
        os.remove(f"uploads/{file.filename}")

        public_key = serialization.load_pem_public_key(session.get('public_key'), backend=default_backend())
        encrypted_ipfs_hash = crypt.encrypt_with_public_key(public_key, ipfs_hash)

        encrypted_ipfs_hash_str = base64.b64encode(encrypted_ipfs_hash).decode("utf-8")
        crypt.store_string(encrypted_ipfs_hash_str)

        fid = crypt.getId()

        conn = connect_to_mysql()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM will WHERE uid = %s", (user_id,))
        conn.commit()

        cursor.execute("INSERT INTO will (uid, fid, will_file) VALUES (%s, %s, %s)",(user_id, fid, file.filename))
        conn.commit()
        conn.close()

        return redirect('/upload_doc9')

@app.route('/retrieve9/<id>', methods=['GET'])
def retrieve9(id):
    filename = request.args.get('filename')

    conn = connect_to_mysql()
    cursor = conn.cursor()
    cursor.execute("SELECT will_file, uid FROM will WHERE fid = %s", (id,))
    file_info = cursor.fetchone()
    conn.close()

    if file_info:
        db_filename, user_id = file_info
        if str(session.get('user_id')) == str(user_id):
            crypt = Crypt()
            retrieved_string = crypt.getString(int(id))

            private_key = serialization.load_pem_private_key(
                session.get('private_key'),
                password=None,
                backend=default_backend()
            )

            try:
                decrypted_ipfs_hash = crypt.decrypt_with_private_key(private_key, base64.b64decode(retrieved_string)).decode('utf-8')
                file_content = crypt.ExtractPdfData(decrypted_ipfs_hash)

                pdf_file = BytesIO(file_content)

                response = make_response(send_file(pdf_file, mimetype='application/pdf'))
                response.headers['Content-Disposition'] = f'attachment; filename={filename}'

                return response
            except ValueError as e:
                return f'Decryption error: {e}', 500
        else:
            return 'Unauthorized', 401
    else:
        return 'File not found', 404
      
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
  
@app.route('/back')
def back():
    session.clear()
    return render_template('/')

if __name__ == '__main__':
    app.run(debug=True)