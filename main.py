'''
Created on 12-Apr-2019

@author: swapnil
'''

import webapp2
import json
import jinja2
import os
import hashlib
import binascii
import logging
import time

from google.appengine.api import app_identity
from google.appengine.api import memcache
from google.appengine.api import mail
from google.appengine.ext import ndb

HN_EMOTIONS_BASE_URL = 'https://hn-emotions.appspot.com'

### Model Start ####
EMOTIONS = ['empathetic', 'encouraging', 'adhominem', 'flame_war', 'discouraging']

EMAIL_RETRY_THRESH = 60

class Emotions(ndb.Model):
    article_id = ndb.IntegerProperty()
    comment_id = ndb.IntegerProperty()
    empathetic = ndb.IntegerProperty(default=0)
    encouraging = ndb.IntegerProperty(default=0)
    adhominem = ndb.IntegerProperty(default=0)
    flame_war = ndb.IntegerProperty(default=0)
    discouraging = ndb.IntegerProperty(default=0)
    future1 = ndb.IntegerProperty(default=0)
    future2 = ndb.IntegerProperty(default=0)
    future3 = ndb.IntegerProperty(default=0)
    future4 = ndb.IntegerProperty(default=0)
    future5 = ndb.IntegerProperty(default=0)

class User(ndb.Model):
    user_id = ndb.StringProperty()
    verification_token = ndb.StringProperty()
    last_tried = ndb.IntegerProperty(default=0)

class UserVote(ndb.Model):
    user_id = ndb.StringProperty()
    comment_id = ndb.IntegerProperty()
    emotions = ndb.StringProperty(repeated=True)

### Model End ####

def send_success_response(response, data, status_code=200):
    response.status_int = status_code
    response.headers['Content-Type'] = 'application/json'
    response.out.write(json.dumps(data))

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

def generate_session_token():
    r = os.urandom(20)
    return binascii.hexlify(r).decode()

class UserHandler(webapp2.RequestHandler):
    @staticmethod
    def send_email(email, token, session):
        confirmation_url = HN_EMOTIONS_BASE_URL + '/user/verify?u=%s&v=%s' % (token, session)
        sender_address = ('Emotions for HN <{}@appspot.gserviceaccount.com>'.format(app_identity.get_application_id()))
        subject = 'Confirm your registration'
        body = """Thank you for showing interest in Emotions!
Please confirm your email address by clicking on the link below:
{}
""".format(confirmation_url)
        mail.send_mail(sender_address, email, subject, body)
    
    def get(self, page):
        if page == 'signup':
            template = JINJA_ENVIRONMENT.get_template('templates/signup.html')
            self.response.write(template.render({}))
        elif page == 'verify':
            user_id = self.request.get('u')
            verification_token = self.request.get('v')

            template = JINJA_ENVIRONMENT.get_template('templates/verified.html')

            if not user_id or not verification_token:
                self.response.write(template.render({ 'error' : 'Email hash or session token doesn\'t exit'}))
                return

            u = ndb.Key('User', user_id).get()
            if u and u.verification_token == verification_token:
                self.response.write(template.render({}))
                self.response.set_cookie('user_id', user_id)
                self.response.set_cookie('verification_token', verification_token)
            else:
                self.response.write(template.render({ 'error' : 'Email hash or session token doesn\'t exit'}))
        elif page == 'valid':
            user_id = self.request.cookies.get('user_id')
            verification_token = self.request.cookies.get('verification_token')

            if not user_id or not verification_token:
                send_success_response(self.response, False)
                return

            u = ndb.Key('User', user_id).get()
            if not u or u.verification_token != verification_token:
                send_success_response(self.response, False)
                return

            send_success_response(self.response, True)

    def post(self, page):
        email = self.request.get('email')
        if not email or not mail.is_email_valid(email):
            template = JINJA_ENVIRONMENT.get_template('templates/signup.html')
            self.response.write(template.render({ 'error' : 'Please provide valid email id' }))
        else:
            current_time = int(time.time())
            
            sha256 = hashlib.sha256()
            sha256.update(email)
            token = sha256.hexdigest()
            session = generate_session_token()

            # limit the rate of email by 1-email/min/user
            u = ndb.Key('User', token).get()
            if u and current_time < (u.last_tried + EMAIL_RETRY_THRESH):
                template = JINJA_ENVIRONMENT.get_template('templates/signup.html')
                self.response.write(template.render({ 'error' : 'Already sent confirmation email. Try after some time.' }))
                return
            
            UserHandler.send_email(email, token, session)
            
            u = User(user_id=token, verification_token=session, last_tried=current_time, id=token)
            u.put()
            
            template = JINJA_ENVIRONMENT.get_template('templates/verify.html')
            self.response.write(template.render({ 'email' : email, 'token' : token}))


class EmotionHandler(webapp2.RequestHandler):
    TTL = 30

    @staticmethod
    def serialize_emotions(emotion=None):
        if emotion:
            return [ 
                emotion.empathetic,  emotion.encouraging, emotion.adhominem, emotion.flame_war, emotion.discouraging,
                emotion.future1,  emotion.future2, emotion.future3, emotion.future4, emotion.future5
            ]
        else:
            return [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    def get(self, article_id, comment_ids):
        comments = comment_ids.split(',')
        
        all_emotions = []
        for comment_id in comments:
            key = '%s_%s' % (article_id, comment_id)

            emotions = memcache.get(key)
            if emotions is None:
                emotions = ndb.Key('Emotions', key).get()
                if emotions:
                    _emotions = EmotionHandler.serialize_emotions(emotions)
                    memcache.add(key, _emotions, EmotionHandler.TTL)
                else:
                    _emotions = EmotionHandler.serialize_emotions()
                    memcache.add(key, _emotions, EmotionHandler.TTL)
                all_emotions += [_emotions]
            else:
                all_emotions += [emotions]
        send_success_response(self.response, all_emotions)

    @staticmethod
    @ndb.transactional
    def insert_if_absent(em_key, emotions):
        fetch = em_key.get()
        if fetch is None:
            emotions.put()
        return fetch
    
    @staticmethod
    def update_emotions(emotions, emotion, unvote):
        if emotion == 'empathetic':
            emotions.empathetic += -1 if unvote else 1 
        elif emotion == 'encouraging':
            emotions.encouraging += -1 if unvote else 1 
        elif emotion == 'adhominem':
            emotions.adhominem += -1 if unvote else 1 
        elif emotion == 'flame_war':
            emotions.flame_war += -1 if unvote else 1 
        elif emotion == 'discouraging':
            emotions.discouraging += -1 if unvote else 1 

    @staticmethod
    @ndb.transactional
    def update_in_trx(em_key, emotion, unvote):
        emotions = em_key.get()
        
        EmotionHandler.update_emotions(emotions, emotion, unvote)
        emotions.put()
        
        return emotions

    def post(self, article_id, comment_id):
        key = '%s_%s' % (article_id, comment_id)
        
        user_id = self.request.cookies.get('user_id')
        verification_token = self.request.cookies.get('verification_token')

        logging.info('%s %s %s' % (key, user_id, verification_token))

        if not user_id or not verification_token:
            self.response.status_int = 400
            return
        
        u = ndb.Key('User', user_id).get()
        if not u or u.verification_token != verification_token:
            self.response.status_int = 400
            return

        emotion = self.request.get('emotion')
        unvote = False

        if emotion not in EMOTIONS:
            # required field missing
            self.response.status_int = 400
            return
        
        try:
            article_id = int(article_id)
            comment_id = int(comment_id)
        except:
            self.response.status_int = 400
            return

        # check whether user has already voted
        vote_key = '%s_%s' % (user_id, comment_id)
        uservote = ndb.Key('UserVote', vote_key).get()
        if uservote:
            if emotion in uservote.emotions:
                self.response.status_int = 400
                return
            else:
                uservote.emotions += [emotion]
                uservote.put()
        else:
            uv = UserVote(user_id=user_id, comment_id=comment_id, emotions=[emotion], id=vote_key)
            uv.put()

        if emotion and emotion.startswith('-'):
            unvote = True
            emotion = emotion[1:]

        # user has not voted yet continue
        em_key = ndb.Key('Emotions', key)
        emotions = em_key.get()
        if not emotions:
            emotions = Emotions(article_id=int(article_id), comment_id=int(comment_id), id=key)
            prev = EmotionHandler.insert_if_absent(em_key, emotions)
            if prev:
                emotions = prev

        EmotionHandler.update_emotions(emotions, emotion, unvote)
        emotions.put()

        _emotions = EmotionHandler.serialize_emotions(emotions)
        memcache.delete(key)
        
        send_success_response(self.response, _emotions)


app = webapp2.WSGIApplication([
    (r'/user/([a-z]+)', UserHandler),
    (r'/emotions/(\d*)/([\d,]*)', EmotionHandler),
], debug=False)
        
