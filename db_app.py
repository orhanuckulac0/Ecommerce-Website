from flask import Flask
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager

from sqlalchemy import Column, Integer, ForeignKey, String
from sqlalchemy.orm import relationship
import stripe

import os
from dotenv import load_dotenv

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_ENDPOINT_SECRET = os.getenv("STRIPE_ENDPOINT_SECRET")

MY_EMAIL = os.getenv("MY_EMAIL")
MY_EMAIL_PASSWORD = os.getenv("MY_EMAIL_PASSWORD")

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
Bootstrap(app)

stripe_keys = {
  'secret_key': STRIPE_SECRET_KEY,
  'publishable_key': STRIPE_PUBLIC_KEY
}
endpoint_secret = STRIPE_ENDPOINT_SECRET
stripe.api_key = stripe_keys['secret_key']

app.config['STRIPE_PUBLIC_KEY'] = STRIPE_PUBLIC_KEY
app.config['STRIPE_SECRET_KEY'] = STRIPE_SECRET_KEY


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///website.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = "static/images/"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGHT"] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

# Base = declarative_base()


class AdminUser(UserMixin, db.Model):
    __tablename__ = "admin_users"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    surname = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    surname = Column(String, nullable=False)
    birthdate = Column(String, nullable=False)
    gender = Column(String, nullable=False)
    phone_number_ext = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)

    user_address = relationship("UserAddresses", backref="user")
    user_billing_address = relationship("UserBillingAddresses", backref="user")
    user_fav = relationship("UserFav", backref="user")
    user_cart = relationship("UserCart", backref="user")
    user_orders = relationship("Orders", backref="user")
    user_returns = relationship("Returns", backref="user")


# add limit to address count of users. Max 5 addresses
class UserAddresses(db.Model):
    __tablename__ = "user_addresses"
    id = Column(Integer, primary_key=True)
    address_title = Column(String, nullable=False)
    address_line = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    postal_code = Column(String, nullable=False)
    country = Column(String, nullable=False)
    name = Column(String, nullable=False)
    surname = Column(String, nullable=False)
    phone_number_ext = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"))


class UserBillingAddresses(db.Model):
    __tablename__ = "user_billing_addresses"
    id = Column(Integer, primary_key=True)
    address_title = Column(String, nullable=False)
    address_line = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    postal_code = Column(String, nullable=False)
    country = Column(String, nullable=False)
    name = Column(String, nullable=False)
    surname = Column(String, nullable=False)
    phone_number_ext = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"))


class UserCart(db.Model):
    __tablename__ = "cart"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, nullable=False)
    product_identifier = Column(String, nullable=False)

    title = Column(String, nullable=False)
    color = Column(String, nullable=True)
    price = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    total_price = Column(Integer, nullable=False)
    main_img_path = Column(String, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"))


class Orders(db.Model):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    order_number = Column(Integer, unique=True, nullable=False)
    product_identifiers = Column(String, nullable=False)

    customer_name = Column(String, nullable=False)
    customer_surname = Column(String, nullable=False)
    delivery_address_ids = Column(Integer, nullable=False)
    billing_address_ids = Column(Integer, nullable=False)

    delivery_cost = Column(Integer, nullable=False)
    total_order_value = Column(Integer, nullable=False)
    order_date = Column(String, nullable=False)
    payment_status = Column(String, nullable=False)
    shipment_status = Column(String, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"))


class OrderDetails(db.Model):
    __tablename__ = "order_details"
    id = Column(Integer, primary_key=True)
    order_number = Column(Integer, nullable=False)
    order_id = Column(Integer, nullable=False)
    product_id = Column(Integer, nullable=False)
    product_identifier = Column(String, nullable=False)

    title = Column(String, nullable=False)
    color = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=True)
    total_price = Column(Integer, nullable=True)
    order_status = Column(String, nullable=False)
    returned_quantity = Column(Integer, nullable=False)

    main_img_path = Column(String, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"))


class CancelledOrders(db.Model):
    __tablename__ = "cancelled_orders"
    id = Column(Integer, primary_key=True)
    order_number = Column(Integer, nullable=False)
    order_id = Column(Integer, nullable=False)
    order_detail_id = Column(Integer, nullable=False)
    product_id = Column(Integer, nullable=False)
    product_identifier = Column(String, nullable=False)

    title = Column(String, nullable=False)
    color = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=True)
    refunded_amount = Column(Integer, nullable=True)
    cancel_date = Column(String, nullable=False)
    main_img_path = Column(String, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"))


class TrackingInformation(db.Model):
    __tablename__ = "tracking_information"
    id = Column(Integer, primary_key=True)
    order_number = Column(Integer, nullable=False)
    order_detail_id = Column(Integer, nullable=False)
    tracking_number = Column(String, nullable=False)
    shipping_company = Column(String, nullable=False)
    expected_delivery_date = Column(String, nullable=False)
    shipment_status = Column(String, nullable=False)
    receiver_name = Column(String, nullable=False)
    receiver_contact_number = Column(String, nullable=False)
    delivery_address = Column(String, nullable=False)
    billing_address = Column(String, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"))


class Returns(db.Model):
    __tablename__ = "returns"
    id = Column(Integer, primary_key=True)
    order_number = Column(Integer, nullable=False)
    order_detail_id = Column(Integer, nullable=False)
    product_id = Column(Integer, nullable=False)
    product_identifier = Column(String, nullable=False)
    product_title = Column(String, nullable=False)
    product_color = Column(String, nullable=False)
    product_price = Column(String, nullable=False)
    returned_quantity = Column(Integer, nullable=False)
    purchased_quantity = Column(Integer, nullable=False)
    total_value = Column(Integer, nullable=False)
    return_reason = Column(String, nullable=False)
    return_date = Column(String, nullable=False)
    approve = Column(String, nullable=True)
    main_img_path = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))


class UserFav(db.Model):
    __tablename__ = "favourites"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, nullable=False)
    product_identifier = Column(String, nullable=False)

    title = Column(String, nullable=False)
    color = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=True)
    total_price = Column(Integer, nullable=True)
    main_img_path = Column(String, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"))


class Products(db.Model):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    product_identifier = Column(String(100), nullable=False)
    variation_type = Column(String, nullable=False)
    child_variation_identifiers = Column(String, nullable=True)

    title = Column(String(300), nullable=False)
    description1 = Column(String(500))
    description2 = Column(String(500))
    description3 = Column(String(500))
    price = Column(Integer, nullable=False)
    stock = Column(Integer, nullable=False)
    color = Column(String(100), nullable=False)
    product_type = Column(String(30), nullable=False)

    file_path = Column(String, nullable=False)

    main_img_path = Column(String, nullable=True)
    second_img_path = Column(String, nullable=True)
    third_img_path = Column(String, nullable=True)
    fourth_img_path = Column(String, nullable=True)
    fifth_img_path = Column(String, nullable=True)


class VariationProducts(db.Model):
    id = Column(Integer, primary_key=True)
    product_identifier = Column(String(100), nullable=False)
    variation_type = Column(String, nullable=False)
    parent_product_id = Column(String, nullable=False)
    parent_product_identifier = Column(String, nullable=False)

    title = Column(String(300), nullable=False)
    description1 = Column(String(500))
    description2 = Column(String(500))
    description3 = Column(String(500))
    price = Column(Integer, nullable=False)
    stock = Column(Integer, nullable=False)
    color = Column(String(100), nullable=False)
    product_type = Column(String(30), nullable=False)

    file_path = Column(String, nullable=False)

    main_img_path = Column(String, nullable=True)
    second_img_path = Column(String, nullable=True)
    third_img_path = Column(String, nullable=True)
    fourth_img_path = Column(String, nullable=True)
    fifth_img_path = Column(String, nullable=True)


db.create_all()
