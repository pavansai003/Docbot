from flask import Flask, render_template, request,  jsonify, session, url_for, redirect
from werkzeug import secure_filename
#from flask.ext.session import Session
import random
import string

import json
import mysql.connector

SESSION_TYPE = 'memcache'
#sess = Session()

# These should be in DB actually
# As this is an assigment, im trying to keep things simple
USER_PROFILE_PIC = "http://aux.iconspalace.com/uploads/1503123125561668860.png"
BOT_PROFILE_PIC = "/static/botpic.png" 

FEEDBACK_LINE = "Your feedback will help us, Thank You!"
BOT_NAME  = "Jarvis"
mydb = mysql.connector.connect(
  host="127.0.0.1",
  user="root",
  passwd="",
  database="product_labs_assignment"
)

app = Flask(__name__)

# This function is like a connector between the ML algorithm and the web app
# It takes the query and gives the reply
def getReplyForQuery(query):
	return "This is supposed to be a reply from the ML algo"
	

def getFileMessageObject(file_url, message,username):
	return {
		'fileUrl':file_url,
		'message':message,
		'type':'file',
		'url': USER_PROFILE_PIC
	}

def getMessageAndReply(message, username, reply):
	message = {
		'message': message,
		'type': "replies",
		'url': 	USER_PROFILE_PIC
	}

	reply = {
		'message' : reply,
		'type': "sent",
		'url': BOT_PROFILE_PIC
	}

	return message, reply

def getFeedbackObject(isUp):
	upstr = 'up' if isUp == 1 else 'down'
	feedback = {
		'message':upstr,
		'type':'like',
		'url':USER_PROFILE_PIC
	}

	feedback_respone = {
		'message': FEEDBACK_LINE,
		'type':"sent",
		'url':BOT_PROFILE_PIC
	}

	return feedback, feedback_respone

def getDocObject(document_name, document_url):
	return {
		'document_name':document_name,
		'document_url':document_url
	}

@app.route('/login',methods=['POST'])
def loginValidate():
	username = request.form.get('username').strip()
	password = request.form.get('password').strip()
	mycursor = mydb.cursor()
	sql = """ SELECT * FROM `users`
				WHERE `username`=%s AND `password` = %s """
	mycursor.execute(sql, (username,password))
	records = mycursor.fetchall()
	
	if len(records) > 0:
		session['userid'] = records[0][0]
		session['loggedin'] = True
		session['username'] = records[0][1]
		return redirect(url_for('home'))
	return render_template("login.html", showError=True)

@app.route('/logout',methods=['GET'])
def logout():
	session.pop('userid')
	session.pop('loggedin')
	session.pop('username')
	return redirect('/login')


@app.route('/login',methods=['GET'])
def login():
	if ('loggedin' not in session) or (session['loggedin'] == False) or (session['userid'] ==None ) :
		return render_template("login.html", showError=False)#redirect('/')
	else:
		return redirect('/')
# Route for home page
@app.route('/')
def home():
	# Check if the user is logged in
	# If the user is not logged in then redirect him to login route
	# validate userid too, just to make sure of any crashes
	#print('loggedin' not in session , session['loggedin'] == False , session['userid']!=None)
	if ('loggedin' not in session) or (session['loggedin'] == False) or (session['userid'] ==None ) :
		return redirect(url_for('login'))
	
	userid = session['userid']
	username =  session['username']
	#Retrieving data for the home(chat) page
	mycursor = mydb.cursor()
	data = {'chat':[]}
	docs_data = {'docs':[]}
	sql = """SELECT p.*, u.username FROM 
				(SELECT c.*, d.userid, d.document_name, d.document_url 
					FROM `chat` c 
					LEFT JOIN `documents` d ON c.document_id = d.document_id) p 
				LEFT JOIN `users` u ON p.userid = u.userid
				WHERE u.userid="""+str(userid)+"""
				ORDER BY p.timestamp ASC"""
	mycursor.execute(sql)
	records = mycursor.fetchall()
	for row in records:
		if row[4] == 1:
			message = getFileMessageObject(row[9],row[2],username)
			data['chat'].append(message)
			docs_data['docs'].append(getDocObject(row[2],row[9]))
		else:
			message, reply = getMessageAndReply(row[2],username,row[3])
			data['chat'].append(message)
			data['chat'].append(reply)

			if row[6] != 0:
				feedback, feedback_respone = getFeedbackObject(row[6])
				data['chat'].append(feedback)
				data['chat'].append(feedback_respone)
   
	return render_template('index.html', data=json.dumps(data), docs_data=json.dumps(docs_data), username=username, userpic=USER_PROFILE_PIC, botname= BOT_NAME, botpic=BOT_PROFILE_PIC )

@app.route('/message')
def reply():
	# print(request.args['message'])
	message = request.args['message']
	#botid = request.args['bot_id']
	doc_id = request.args['doc_id']
	reply  = getReplyForQuery(message)
	mycursor = mydb.cursor()
	# sql = "INSERT INTO customers (name, address) VALUES (%s, %s)"
	sql = """INSERT INTO `chat`
				( `document_id`,  `message`, `reply`) VALUES 
				( %s,  %s, %s)"""
	val = ( doc_id ,  message, reply)
	mycursor.execute(sql, val)
	mydb.commit()
	return reply

@app.route('/feedback')
def feedback():
	feedback = 1 if request.args['thumps'] == "up" else -1
	sql = "UPDATE `chat` SET `feedback`="+str(feedback)+" WHERE `message_id` = (SELECT `message_id` FROM (SELECT * FROM `chat`) AS c ORDER BY c.`message_id` DESC LIMIT 1 )"
	mycursor = mydb.cursor()
	mycursor.execute(sql)
	mydb.commit()
	return FEEDBACK_LINE

@app.route('/upload', methods = ['GET', 'POST'])
def upload_file():
	if request.method == 'POST':
		f = request.files['file']
		x = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(8))
		actfile = secure_filename(f.filename)
		savepath = 'static/uploads/'+x+'_'+actfile
		f.save(savepath)
		mycursor = mydb.cursor()
		sql = """INSERT INTO `documents`
					(`document_name`, `document_url`, `userid`)
					VALUES (%s, %s, %s)"""
		val = (actfile, savepath, session['userid'])
		mycursor.execute(sql, val)
		mydb.commit()
		doc_id = mycursor.lastrowid
		sql = """INSERT INTO `chat`
				( `document_id`, `message`, `isFile`, `reply`)
				VALUES (%s, %s, %s, %s) """
		val = ( doc_id, actfile, 1, '')
		mycursor.execute(sql, val)
		mydb.commit()
		return jsonify({'url':savepath, 'doc_id':doc_id })

if __name__ == '__main__':
	app.secret_key = 'lololol'
	#sess.init_app(app)
	app.config['SESSION_TYPE'] = 'filesystem'
	app.static_url_path=app.config.get('STATIC_FOLDER')
	app.static_folder = app.root_path + app.static_url_path
	app.run()