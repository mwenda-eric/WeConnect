from flask import Flask, Blueprint, jsonify, request, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import jwt
import re
import uuid
import datetime
import os
from app.models.v1 import User, Business, Reviews

# create a version 1 blueprint
version1 = Blueprint('v1', __name__)


# instance of model that will store app data
# application will use data structures to srore data
user_model = User()
business_model = Business()
review_model = Reviews()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'access-token' not in request.headers:
            return jsonify({
                'message': 'Token is missing, login to get token'
            }), 401
        try:
            token = request.headers['access-token']
            data = jwt.decode(token, os.getenv("SECRET_KEY"))
            if data['username'] in user_model.user_token:
                current_user = user_model.users[data['username']]
            else:
                return jsonify({"message": "You are not logged in"}), 401
        except:
            return jsonify({'message': 'Token is invalid or Expired!'}), 401

        return f(current_user, *args, **kwargs)
    return decorated


@version1.route('auth/register', methods=['POST'])
def register():
    """Route to create user, it will receive data through a post method"""
    try:
        data = request.get_json()  # get data from the api consumer
        if not data or not data['username'].strip() or not data["password"]:
            return jsonify({'message': "username or password missing"})
        if not re.match(r'\A[0-9a-zA-Z!@#$%&*]{6,20}\Z', data['password']):
            return jsonify({"Message": "Password must be 6-20 Characters"}), 406
        if data['username'].strip() in user_model.users:  # test if username exists
            return jsonify({"message": "Sorry!! Username taken!"})
        hashed_password = generate_password_hash(data['password'], method='sha256')
        user = user_model.add_user(data['username'].strip(),hashed_password,
                                   data['first_name'],
                                   data['last_name'])
        return jsonify({"message": "user created!", "Details": 
            {"id": user['id'],"username": user['username'],
                "first_name": user['first_name'],"last_name": user['last_name']
            }}), 201
    except Exception as e:
        return jsonify({
            "Error": "Error!, check you are sending correct information"}), 400

@version1.route('auth/login', methods=['POST'])
def login():
    """login route. users will login to the app via this route"""
    try:
        auth = request.get_json()
        if not auth or not auth['username'].strip() or not auth['password']:
            return jsonify({"message": "login required!"}), 401
        if auth['username'].strip() not in user_model.users.keys():
            return jsonify({"message": "Username not found!"}), 401
        user = user_model.users[auth['username'].strip()]
        if check_password_hash(user['password'], auth['password']):
            token = jwt.encode({
                'username': user['username'],
                'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=1000)},
                os.getenv("SECRET_KEY")
            )
            user_model.user_token[user['username']] = token.decode('UTF-8')
            return jsonify({"auth_token": token.decode('UTF-8')}), 200
        return jsonify({"message": "Wrong password!"}), 401
    except Exception as e:
        return jsonify({
            "Error": "Error!, check you are sending correct information"}), 400


@version1.route('auth/logout', methods=['POST'])
@login_required
def logout(current_user):
    """method to logout user"""
    try:
        token = request.headers['access-token']
        data = jwt.decode(token, os.getenv("SECRET_KEY"))
        if data['username'] in user_model.user_token.keys():
            del user_model.user_token[data['username']]
            return jsonify({"message": "Logged out!"}), 200
    except:
        return jsonify({'message': 'Invalid token!'})


@version1.route('auth/reset-password', methods=['PUT'])
@login_required
def reset_password(current_user):
    """Reset password for users"""
    try:
        data = request.get_json()
        if not data['password']:
            return jsonify({"message": "Password is required"})
        if not re.match(r'\A[0-9a-zA-Z!@#$%&*]{6,20}\Z', data['password']):
            return jsonify({
                "Message": "Password must be 6-20 Characters and can only contains leters,numbers,and any of !@#$%"
            }), 406
        if check_password_hash(current_user['password'], data['old_password']):
            hashed_password = generate_password_hash(
                data['password'].strip(), method='sha256')
            usr = user_model.users[current_user["username"]]
            usr.update({"password": hashed_password})
            return jsonify({"message": "password updated"})
        return jsonify({"message": "Wrong old Password"}), 406
    except Exception as e:
        return jsonify({
            "Error": "Error!, check you are sending correct information"
        }), 400


@version1.route('businesses', methods=['POST'])
@login_required
def register_business(current_user):
    """endpoint to create a new business"""
    try:
        data = request.get_json()
        if not data or not data['name'].strip():
            return jsonify({"message": "Name cannot be empty!"}), 401
        for busines in business_model.businesses.values():
            if data['name'].strip() == busines['name']:
                return jsonify({"message": "Sorry!! Name taken!"}), 401
        # update business
        user_id = current_user['username']
        create = business_model.add_businesses(data['name'].strip(),
                                               data['location'], data['category'], data['bio'], user_id)
        return jsonify({
            "message": "Business created", 'business': create
        }), 201
    except Exception as e:
        return jsonify({
            "Error": "Error!, check you are sending correct information"
        }), 400

@version1.route('businesses/<businessId>', methods=['PUT'])
@login_required
def update_business(current_user, businessId):
    """ Get business id and update business"""
    try:
        if businessId not in business_model.businesses:
            return jsonify({"message": "Business not found"})
        biz = business_model.businesses[businessId]
        data = request.get_json()
        if biz['user_id'] == current_user['username']:
            biz['location'] = data['location'].strip()
            biz['category'] = data['category'].strip()
            biz['name'] = data['name'].strip()
            biz['bio'] = data['bio'].strip()
            return jsonify({
                "message": "business updated!",
                "business": biz
            }), 202
        return jsonify({
            "message": "Sorry! You can only update your business!!"}), 401
    except Exception as e:
        return jsonify({
            "Error": "Error!, check you are sending correct information"
        })


@version1.route('businesses', methods=['GET'])
def get_busineses():
    """Returns all registered businesses"""
    return jsonify(business_model.businesses)


@version1.route('businesses/<businessId>', methods=['DELETE'])
@login_required
def delete_business(current_user, businessId):
    """ deletes a business"""
    if businessId in business_model.businesses:
        bs = business_model.businesses[businessId]
        if bs['user_id'] == current_user['username']:
            del business_model.businesses[businessId]
            return jsonify({
                "message": "Business Deleted",
                "Deleted Details": bs
            }), 201
        return jsonify({
            "message": "Sorry! You can only delete your business!!"
        }), 401
    return jsonify({"message": "Business not found"}), 401


@version1.route('businesses/<business_id>', methods=['GET'])
def get_business(business_id):
    """ returns a single business"""
    if business_id in business_model.businesses:
        data = business_model.businesses[business_id]
        return jsonify(data)
    return jsonify({"message": "Business not found"}), 401


@version1.route('businesses/<businessId>/reviews', methods=['POST'])
@login_required
def create_review(current_user, businessId):
    """ Add revies to a business. only logged in users"""
    try:
        data = request.get_json()
        if not data or not data['review'] or not data['title']:
            return jsonify({
                "message": "Please provide all required fields"
            }), 401
        if businessId not in business_model.businesses:
            return jsonify({
                "message": "Business not found"
            }), 401
        user_id = current_user['username']
        review_model.add_review(data['review'], user_id, businessId)
        return jsonify({
            "message": "Your Review was added"
        }), 201
    except Exception as e:
        return jsonify({
            "Error": "Error!, check you are sending correct information"
        }), 400

@version1.route('businesses/<businessId>/reviews', methods=['GET'])
def get_business_reviews(businessId):
    """Gets all reviews for a business"""
    if businessId not in business_model.businesses:
        return jsonify({
            "message": "Business not found"
        })
    all_reviews = []
    for review in review_model.reviews.values():
        if review['business_id'] == businessId:
            all_reviews.append(review)
    if not all_reviews:
        return jsonify({"message": "No Reviews for this business"})
    return jsonify(all_reviews)
    # for review in review_model.reviews:
