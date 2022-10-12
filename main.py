import sqlalchemy.exc

from flask import render_template, redirect, url_for, flash, request, session, jsonify, abort
from flask_login import login_user, current_user, logout_user, login_required

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from db_app import app, db, login_manager, User, AdminUser, UserAddresses, UserBillingAddresses, UserCart, UserFav, \
    Products, VariationProducts, Orders, OrderDetails, Returns, CancelledOrders, TrackingInformation, \
    stripe_keys, endpoint_secret

from functions import order_num, current_date, generate_random_code, send_verification
from order_related_functions import add_order_details

import os
import stripe
from stripe import error

import logging
from uuid import uuid4
from functools import wraps

UPLOAD_FOLDER = "static/images/"
BASE_PATH = ""
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}


# # # # # # # #  DECORATORS  # # # # # # # #
@login_manager.user_loader
def load_user(user_id):
    if int(user_id) > 1000:
        return AdminUser.query.get(int(user_id))
    else:
        return User.query.get(int(user_id))


def admin_only(func):
    @wraps(func)
    def check_id(*args, **kwargs):
        if int(current_user.id) < 1000:
            raise abort(403)
        else:
            return func(*args, **kwargs)

    return check_id


# # # # # # # # # # # # # # # # # # # # # # ----USER RELATED----  # # # # # # # # # # # # # # # # # # # # # #
# # # # # # # #  USER PROFILE ROUTE FUNCTIONS # # # # # # # #
@app.route("/")
def home():
    if current_user.is_authenticated:
        user_name = current_user.name.capitalize()
        p_products_all = Products.query.all()
        v_products_all = VariationProducts.query.all()
        products_all = []
        for p in p_products_all:
            products_all.append(p)
        for v in v_products_all:
            products_all.append(v)
        return render_template("index.html", name=user_name, products=products_all)
    else:
        products_all = Products.query.all()
        return render_template("index.html", products=products_all)


@app.route("/profile")
@login_required
def profile():
    orders = Orders.query.filter_by(user_id=current_user.id).all()
    order_details = OrderDetails.query.filter_by(user_id=current_user.id).all()
    return render_template("profile.html",
                           orders=orders,
                           order_details=order_details,
                           )


@app.route("/favourites", methods=["GET", "POST"])
def favourites():
    if current_user.is_authenticated:
        user_favs = UserFav.query.filter_by(user_id=current_user.id).all()
        if len(user_favs) == 0:
            user_favs = "empty"
        products_all = Products.query.all()
        return render_template("favourites.html", fav_products=user_favs, products_all=products_all)
    else:
        return redirect(url_for("login"))


@app.route("/product/show/<id>/<product_identifier>/", methods=["GET", "POST"])
def handle_user(id, product_identifier):
    if current_user.is_authenticated:
        current_product = Products.query.filter_by(id=id, product_identifier=product_identifier).first()
        if current_product is None:
            current_product = VariationProducts.query.filter_by(
                id=id,
                product_identifier=product_identifier).first()
        activity_val = request.form.get("activity")
        color = current_product.color
        quantity = request.form.get("quantity")
        price = request.form.get("price")
        if quantity is None:
            quantity = 0
            total_price = float(price) * 1
        else:
            total_price = float(price) * float(quantity)
        if activity_val == "add_fav":
            return redirect(url_for("add_fav",
                                    product_id=id,
                                    product_identifier=current_product.product_identifier,
                                    color=color,
                                    price=price,
                                    quantity=quantity,
                                    total_price=total_price,
                                    )
                            )
        elif activity_val == "remove_fav":
            fav_product = UserFav.query.filter_by(product_id=id, product_identifier=product_identifier).first()
            return redirect(url_for("remove_fav",
                                    product_id=fav_product.product_id,
                                    product_identifier=fav_product.product_identifier,
                                    user_id=current_user.id
                                    )
                            )

        elif activity_val == "add_to_cart":
            return redirect(url_for("add_to_cart",
                                    product_id=current_product.id,
                                    product_identifier=current_product.product_identifier,
                                    color=color,
                                    price=price,
                                    quantity=quantity,
                                    total_price=total_price
                                    )
                            )
    else:
        return redirect(url_for("login"))


@app.route("/favourites/add_fav/<product_id>/<product_identifier>/<color>/<price>/<quantity>/<total_price>/",
           methods=["GET", "POST"])
def add_fav(product_id, product_identifier, color, price, quantity, total_price):
    if current_user.is_authenticated:
        check_product = UserFav.query.filter_by(product_id=product_id,
                                                product_identifier=product_identifier,
                                                user_id=current_user.id).first()
        if check_product is not None:
            check_product.quantity += 1
            check_product.total_price += check_product.price
            db.session.commit()
            return redirect(request.referrer)

        else:
            fav_product = Products.query.filter_by(id=product_id, product_identifier=product_identifier).first()
            if fav_product is None:
                fav_product = VariationProducts.query.filter_by(id=product_id,
                                                                product_identifier=product_identifier).first()

            if color == "None Selected":
                color = [color for color in fav_product.color.split()][0]
            new_fav = UserFav(
                title=fav_product.title,
                product_identifier=fav_product.product_identifier,
                color=color,
                price=price,
                quantity=quantity,
                total_price=total_price,
                main_img_path=fav_product.main_img_path,
                product_id=fav_product.id,
                user_id=current_user.id,
            )
            db.session.add(new_fav)
            db.session.commit()
            return redirect(request.referrer)
    else:
        return redirect(url_for("login"))


@app.route("/favourites/remove_fav/<product_id>/<product_identifier>/<user_id>/", methods=["GET", "POST"])
@login_required
def remove_fav(product_id, product_identifier, user_id):
    if current_user.is_authenticated:
        UserFav.query.filter_by(product_id=product_id,
                                product_identifier=product_identifier,
                                user_id=user_id).delete()
        db.session.commit()
        return redirect(request.referrer)
    else:
        return redirect(url_for("favourites"))


@app.route("/favourites/edit_fav/<fav_id>/<product_identifier>/<user_id>", methods=["GET", "POST"])
@login_required
def edit_fav(fav_id, product_identifier, user_id):
    if request.method == "POST":
        current_fav_product = UserFav.query.filter_by(id=fav_id,
                                                      product_identifier=product_identifier,
                                                      user_id=user_id).first()
        current_fav_product.quantity = int(request.form.get("quantity"))
        current_fav_product.total_price = current_fav_product.quantity * current_fav_product.price
        db.session.commit()
        return redirect(request.referrer)
    else:
        return redirect(request.referrer)


@app.route("/favourites/fav_to_cart/<fav_id>/<product_id>/<product_identifier>/<user_id>")
@login_required
def fav_to_cart(fav_id, product_id, product_identifier, user_id):
    if current_user.is_authenticated:

        # check if the current product is out of stock before adding it to the cart
        current_product = Products.query.filter_by(id=product_id, product_identifier=product_identifier).first()
        if current_product is None:
            current_product = VariationProducts.query.filter_by(id=product_id,
                                                                product_identifier=product_identifier).first()
        if current_product.stock == 0:
            return redirect(request.referrer)
        current_fav_product = UserFav.query.filter_by(id=fav_id,
                                                      product_id=product_id,
                                                      product_identifier=product_identifier,
                                                      user_id=user_id).first()

        if current_fav_product.color == "None Selected":
            flash("To send this item to your cart, you need to select color", "cart")
            flash("Click to yellow edit button to update your order", "cart")
            return redirect(request.referrer)
        new_cart = UserCart(
            title=current_fav_product.title,
            product_identifier=current_fav_product.product_identifier,
            price=current_fav_product.price,
            color=current_fav_product.color,
            quantity=current_fav_product.quantity,
            total_price=current_fav_product.total_price,
            main_img_path=current_fav_product.main_img_path,
            product_id=current_fav_product.product_id,
            user_id=current_fav_product.user_id
        )
        db.session.add(new_cart)
        UserFav.query.filter_by(id=fav_id,
                                product_id=product_id,
                                product_identifier=product_identifier,
                                user_id=user_id).delete()
        db.session.commit()
        return redirect(request.referrer)
    else:
        return redirect(request.referrer)


@app.route("/profile-settings/", methods=["GET", "POST"])
@login_required
def profile_settings():
    if current_user.is_authenticated:
        if request.method == "POST":
            update_user = User.query.filter_by(id=current_user.id).first()
            update_user.name = request.form.get("name")
            update_user.surname = request.form.get("surname")
            update_user.phone_number_ext = request.form.get("phone_number_ext")
            update_user.phone_number = request.form.get("phone_number")
            update_user.birthdate = request.form.get("birthdate")
            update_user.email = request.form.get("email")

            db.session.commit()

            return redirect(url_for("profile_settings"))
        return render_template("profile_settings.html", user=current_user)


@app.route("/profile-settings/<status>", methods=["GET", "POST"])
@login_required
def change_password(status):
    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    if status == "True":
        user = User.query.filter_by(id=current_user.id).first()
        current_password_entered = request.form.get("current_password")
        if check_password_hash(user.password, current_password_entered):
            new_pw = request.form.get("new_password")
            new_pw_repeat = request.form.get("new_password_repeat")
            if new_pw == new_pw_repeat:
                hashed_pw = generate_password_hash(password=new_pw,
                                                   method="pbkdf2:sha256",
                                                   salt_length=8)
                user.password = hashed_pw
                db.session.commit()
                flash("Password has been changed.", "password_flash")
                return redirect(url_for("profile_settings"))
            else:
                flash("New passwords does not match.", "password_flash")
                return redirect(url_for("profile_settings"))
        else:
            flash("You entered your current password wrong.", "password_flash")
            return redirect(url_for("profile_settings"))
    return redirect(url_for("profile_settings"))


@app.route("/verify-email/", methods=["GET", "POST"])
def verify_email():
    if request.method == "POST":
        user_email = request.form.get("email")
        if User.query.filter_by(email=user_email).first():
            random_code = generate_random_code()
            send_verification(user_email, random_code)
            session["email"] = user_email
            return render_template("verify_code.html")
        else:
            flash("Email is not used. Please try again.", "verify_email")
            return redirect(request.referrer)
    return render_template("verify_email.html")


@app.route("/verify-code/", methods=["GET", "POST"])
def verify_code():
    if request.method == "POST":
        code_entered = request.form.get("code")
        try:
            if int(code_entered) == session["code"]:
                return render_template("setup_new_password.html")
            else:
                flash("You entered a wrong code. Please try again.", "verify_code")
                return render_template("verify_code.html")
        except ValueError:  # just in case..
            print("User entered a str with copy paste.")
            print(f"Email of this user: {session['email']}")
            flash("Please do not try to use malicious text.", "verify_code")
            return render_template("verify_code.html")


@app.route("/setup_new_password/", methods=["GET", "POST"])
def setup_new_password():
    if request.method == "POST":
        password = request.form.get("password")
        password_repeat = request.form.get("password_repeat")
        if password == password_repeat:
            hashed_pw = generate_password_hash(password=password, method="pbkdf2:sha256", salt_length=8)
            user = User.query.filter_by(email=session["email"]).first()
            user.password = hashed_pw
            db.session.commit()
            return redirect(url_for("login"))
        else:
            return redirect(request.referrer)
    return redirect(request.referrer)


@app.route("/addresses/")
@login_required
def user_addresses():
    """Display user addresses"""
    addresses = UserAddresses.query.filter_by(user_id=current_user.id).all()
    return render_template("user_addresses.html", address_list=addresses)


@app.route("/billing_addresses/")
@login_required
def user_billing_addresses():
    """Display user addresses"""
    billing_addresses = UserBillingAddresses.query.filter_by(user_id=current_user.id).all()
    return render_template("user_billing_addresses.html", billing_address_list=billing_addresses)


@app.route("/addresses/", methods=["GET", "POST"])
@login_required
def add_user_address():
    if request.method == "POST":
        if request.form.get("address_type") == "delivery":
            new_user_address = UserAddresses(
                address_title=request.form.get("address_title"),
                address_line=request.form.get("address_line"),
                city=request.form.get("city"),
                state=request.form.get("state"),
                postal_code=request.form.get("postal_code"),
                country=request.form.get("country"),
                name=request.form.get("name"),
                surname=request.form.get("surname"),
                phone_number_ext=request.form.get("phone_number_ext"),
                phone_number=request.form.get("phone_number"),
                user_id=current_user.id,
            )
            db.session.add(new_user_address)
            db.session.commit()
            return redirect(request.referrer)

        elif request.form.get("address_type") == "billing":
            new_user_billing_address = UserBillingAddresses(
                address_title=request.form.get("address_title"),
                address_line=request.form.get("address_line"),
                city=request.form.get("city"),
                state=request.form.get("state"),
                postal_code=request.form.get("postal_code"),
                country=request.form.get("country"),
                name=request.form.get("name"),
                surname=request.form.get("surname"),
                phone_number_ext=request.form.get("phone_number_ext"),
                phone_number=request.form.get("phone_number"),
                user_id=current_user.id,
            )
            db.session.add(new_user_billing_address)
            db.session.commit()
            return redirect(request.referrer)
    else:
        return redirect(request.referrer)


@app.route("/addresses/delete/<address_id>/<address_type>/", methods=["GET", "POST"])
@login_required
def delete_address(address_id, address_type):
    user = User.query.filter_by(id=current_user.id).first().id
    if address_type == "delivery":
        address_owner = UserAddresses.query.filter_by(id=address_id).first().user_id
        if user == address_owner:
            UserAddresses.query.filter_by(id=address_id).delete()
            db.session.commit()
            return redirect(request.referrer)
        else:
            return redirect(request.referrer)

    elif address_type == "billing":
        billing_address_owner = UserBillingAddresses.query.filter_by(id=address_id).first().user_id
        if user == billing_address_owner:
            UserBillingAddresses.query.filter_by(id=address_id).delete()
            db.session.commit()
            return redirect(request.referrer)
        else:
            return redirect(request.referrer)


@app.route("/addresses/edit/<address_id>/<address_type>", methods=["GET", "POST"])
@login_required
def edit_address(address_id, address_type):
    if current_user.is_authenticated:
        if request.method == "POST":
            if address_type == "delivery":
                current_address = UserAddresses.query.filter_by(id=address_id, user_id=current_user.id)
                current_address.update({UserAddresses.address_title: request.form.get("address_title")})
                current_address.update({UserAddresses.address_line: request.form.get("address_line")})
                current_address.update({UserAddresses.city: request.form.get("city")})
                current_address.update({UserAddresses.state: request.form.get("state")})
                current_address.update({UserAddresses.postal_code: request.form.get("postal_code")})
                current_address.update({UserAddresses.country: request.form.get("country")})
                current_address.update({UserAddresses.name: request.form.get("name")})
                current_address.update({UserAddresses.surname: request.form.get("surname")})
                current_address.update({UserAddresses.phone_number_ext: request.form.get("phone_number_ext")})
                current_address.update({UserAddresses.phone_number: request.form.get("phone_number")})
                db.session.commit()
                return redirect(request.referrer)

            elif address_type == "billing":
                current_address = UserBillingAddresses.query.filter_by(id=address_id, user_id=current_user.id)
                current_address.update({UserBillingAddresses.address_title: request.form.get("address_title")})
                current_address.update({UserBillingAddresses.address_line: request.form.get("address_line")})
                current_address.update({UserBillingAddresses.city: request.form.get("city")})
                current_address.update({UserBillingAddresses.state: request.form.get("state")})
                current_address.update({UserBillingAddresses.postal_code: request.form.get("postal_code")})
                current_address.update({UserBillingAddresses.country: request.form.get("country")})
                current_address.update({UserBillingAddresses.name: request.form.get("name")})
                current_address.update({UserBillingAddresses.surname: request.form.get("surname")})
                current_address.update({UserBillingAddresses.phone_number_ext: request.form.get("phone_number_ext")})
                current_address.update({UserBillingAddresses.phone_number: request.form.get("phone_number")})
                db.session.commit()
                return redirect(request.referrer)
        else:
            return redirect(request.referrer)
    else:
        return redirect(url_for("login"))


# # # # # # # #  PAYMENT / ORDER ROUTES  # # # # # # # #
@app.route("/cart/", methods=["GET", "POST"])
def cart():
    if current_user.is_authenticated:
        cart_items_all = UserCart.query.filter_by(user_id=current_user.id).all()
        cart_len = len(cart_items_all)
        total = 0
        for t_price in cart_items_all:
            total += t_price.total_price
        products_all = Products.query.all()
        return render_template("cart.html",
                               cart=cart_items_all,
                               item_count=cart_len,
                               total=round(total, 2),
                               products_all=products_all)
    else:
        return redirect(url_for("login"))


@app.route("/add_to_cart/<product_id>/<product_identifier>/<color>/<price>/<quantity>/<total_price>/",
           methods=["GET", "POST"])
def add_to_cart(product_id, product_identifier, color, price, quantity, total_price):
    if current_user.is_authenticated:
        product_to_add = Products.query.filter_by(product_identifier=product_identifier).first()
        if product_to_add is None:
            product_to_add = VariationProducts.query.filter_by(product_identifier=product_identifier).first()

        # check if the item is already in cart
        check_cart_item = UserCart.query.filter_by(product_identifier=product_to_add.product_identifier,
                                                   user_id=current_user.id).first()
        if check_cart_item is not None:
            check_cart_item.quantity += int(quantity)
            check_cart_item.total_price += check_cart_item.price
            db.session.commit()
            return redirect(request.referrer)
        else:
            if color == "None Selected":
                color = [color for color in product_to_add.color.split()][0]

            cart_item = UserCart(
                product_identifier=product_to_add.product_identifier,
                title=product_to_add.title,
                color=color,
                price=price,
                quantity=quantity,
                total_price=round(float(total_price), 2),
                main_img_path=product_to_add.main_img_path,
                product_id=product_id,
                user_id=current_user.id
            )
            db.session.add(cart_item)
            db.session.commit()
            return redirect(request.referrer)
    else:
        return redirect(url_for("login"))


@app.route("/cart/delete/<cart_id>/<product_id>/<product_identifier>/<user_id>", methods=["GET", "POST"])
@login_required
def delete_from_cart(cart_id, product_id, product_identifier, user_id):
    user = User.query.filter_by(id=user_id).first().id
    if current_user.is_authenticated:
        if user == current_user.id:
            UserCart.query.filter_by(id=cart_id,
                                     product_id=product_id,
                                     product_identifier=product_identifier,
                                     user_id=user).delete()
            db.session.commit()
            return redirect(request.referrer)
        else:
            return redirect(url_for("cart"))
    else:
        return redirect(url_for("login"))


@app.route("/cart/cart_to_fav/<cart_id>/<product_id>/<product_identifier>/<user_id>", methods=["GET", "POST"])
@login_required
def cart_to_fav(cart_id, product_id, product_identifier, user_id):
    if current_user.is_authenticated:
        cart_product = UserCart.query.filter_by(id=cart_id,
                                                product_id=product_id,
                                                product_identifier=product_identifier,
                                                user_id=user_id).first()

        check_product = UserFav.query.filter_by(product_identifier=product_identifier, user_id=current_user.id).first()
        if check_product is not None:
            check_product.quantity += cart_product.quantity
            check_product.total_price += check_product.price
            UserCart.query.filter_by(id=cart_id, product_id=product_id, user_id=user_id).delete()
            db.session.commit()
            return redirect(request.referrer)
        else:
            new_fav = UserFav(
                title=cart_product.title,
                product_identifier=product_identifier,
                color=cart_product.color,
                price=cart_product.price,
                quantity=cart_product.quantity,
                total_price=float(cart_product.price) * float(cart_product.quantity),
                main_img_path=cart_product.main_img_path,
                product_id=product_id,
                user_id=user_id
            )
            db.session.add(new_fav)
            UserCart.query.filter_by(id=cart_id, product_id=product_id, user_id=user_id).delete()
            db.session.commit()
            return redirect(request.referrer)
    else:
        return redirect(request.referrer)


@app.route("/cart/edit_cart/<cart_id>/<product_id>/<product_identifier>/<user_id>", methods=["GET", "POST"])
def edit_cart(cart_id, product_id, product_identifier, user_id):
    if request.method == "POST":
        cart_product = UserCart.query.filter_by(
            id=cart_id,
            product_id=product_id,
            product_identifier=product_identifier,
            user_id=user_id).first()
        cart_product.quantity = int(request.form.get("quantity"))
        cart_product.total_price = round(float(cart_product.quantity * cart_product.price), 2)
        db.session.commit()
        return redirect(request.referrer)


@app.route("/checkout/")
@login_required
def checkout():
    if current_user.is_authenticated:
        user = User.query.filter_by(id=current_user.id).first

        user_address_list = UserAddresses.query.filter_by(user_id=current_user.id).all()
        user_billing_address_list = UserBillingAddresses.query.filter_by(user_id=current_user.id).all()
        user_cart_list = UserCart.query.filter_by(user_id=current_user.id).all()
        total_price = 0
        for t_price in user_cart_list:
            total_price += t_price.total_price

        return render_template("checkout.html",
                               user=user,
                               user_addresses=user_address_list,
                               user_billing_addresses=user_billing_address_list,
                               user_cart=user_cart_list,
                               user_cart_len=len(user_cart_list),
                               total_price=round(total_price, 2),
                               key=stripe_keys['publishable_key'],
                               )
    else:
        return redirect(url_for("login"))


# # # # # # # #  ORDER and PAYMENT RELATED ROUTES / FUNCTIONS # # # # # # # #


@app.route("/checkout/order_now/<user_id>/<amount>/", methods=["GET", "POST"])
@login_required
def make_purchase(user_id, amount):
    if request.method == "POST":
        if current_user.is_authenticated:
            # First charge the payment, then add the order to db
            # Amount in cents
            cost = round(float(amount) * 100)
            try:
                customer = stripe.Customer.create(
                    email='customer@example.com',
                    source=request.form['stripeToken']
                )

                charge = stripe.Charge.create(
                    customer=customer.id,
                    amount=cost,
                    currency='usd',
                    description='Purchase Payment'
                )
                if charge.status == "succeeded":
                    logging.info("successful transaction")
                    user = User.query.filter_by(id=user_id).first()
                    cart_items_all = UserCart.query.filter_by(user_id=user.id).all()

                    total_order_value = 0
                    for t_price in cart_items_all:
                        total_order_value += t_price.total_price

                    order_item_product_identifiers_list = [p.product_identifier for p in cart_items_all]
                    order_item_product_identifiers = "".join(str(p) + " " for p in order_item_product_identifiers_list)

                    order_number = order_num()
                    delivery_address_id = request.form.get("delivery_address")
                    billing_address_id = request.form.get("billing_address")

                    new_order = Orders(
                        order_number=order_number,
                        product_identifiers=order_item_product_identifiers,
                        customer_name=user.name,
                        customer_surname=user.surname,
                        delivery_address_ids=delivery_address_id,
                        billing_address_ids=billing_address_id,
                        delivery_cost=0,
                        total_order_value=round(total_order_value, 2),
                        order_date=current_date(),
                        payment_status=charge.status,
                        shipment_status="Being Prepared",
                        user_id=current_user.id
                    )
                    db.session.add(new_order)
                    db.session.commit()

                    add_order_details(cart_items_all, order_number, user_id)
                    logging.info("No error.")

                    # create dict of title X quantity: cost

                    purchased_info = {}
                    for p in cart_items_all:
                        purchased_info[f"{p.title} x {p.quantity}"] = p.total_price
                    print(purchased_info)

                    return render_template("charge.html",
                                           amount=amount,
                                           user_name=current_user.name + " " + current_user.surname,
                                           products=purchased_info,
                                           order_number=order_number,
                                           order_date=current_date()
                                           )

                elif charge.status == "pending":
                    logging.error("pending payment")

                elif charge.status == "failed":
                    logging.error("payment failed")
                    payment_error(charge.status)

            except stripe.error.CardError as ex:
                logging.error("A payment error occurred: {}".format(ex.user_message))
                payment_error(ex.user_message)

            except stripe.error.InvalidRequestError:
                logging.error("An invalid request occurred.")
                payment_error("An invalid request occurred")

            except Exception as ex:
                template = "An exception of type {0} occurred. Arguments:\n{1!r}"
                message = template.format(type(ex).__name__, ex.args)
                logging.error("Another problem occurred, maybe unrelated to Stripe.")
                payment_error(message)

            # finally:
            #     return render_template('charge.html', amount=cost)
        return redirect(request.referrer)
    return redirect(request.referrer)


@app.route("/payment_error/<exception>/", methods=["GET"])
def payment_error(exception):
    logging.error(exception)
    return render_template("payment_error.html", exception=exception)


@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.data
    sig_header = request.headers['STRIPE_SIGNATURE']

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        raise e
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise e

    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        print(payment_intent)
    # ... handle other event types
    else:
        print('Unhandled event type {}'.format(event['type']))

    return jsonify(success=True)


@app.route("/order-details/<order_number>/", methods=["GET", "POST"])
def order_detail_page(order_number):
    if current_user.is_authenticated:
        orders = Orders.query.filter_by(user_id=current_user.id).all()
        order_details = OrderDetails.query.filter_by(order_number=order_number, user_id=current_user.id).all()

        user_returns = Returns.query.filter_by(user_id=current_user.id).all()
        return_det_ids = [r.order_detail_id for r in user_returns]

        current_order = Orders.query.filter_by(order_number=order_number, user_id=current_user.id).first()
        delivery_address_id = current_order.delivery_address_ids
        delivery_address = UserAddresses.query.filter_by(user_id=current_user.id, id=delivery_address_id).first()

        billing_address_id = current_order.billing_address_ids
        billing_address = UserBillingAddresses.query.filter_by(user_id=current_user.id, id=billing_address_id).first()

        order_tracking = TrackingInformation.query.filter_by(order_number=order_number, user_id=current_user.id).all()

        return render_template("order_detail_page.html",
                               orders=orders,
                               order_details=order_details,
                               order_number=order_number,
                               returns=user_returns,
                               return_det_ids=return_det_ids,
                               delivery_address=delivery_address,
                               billing_address=billing_address,
                               order_tracking=order_tracking
                               )


@app.route("/order_tracking/<order_number>/<order_detail_id>/<user_id>/", methods=["GET"])
def order_tracking_page(order_number, order_detail_id, user_id):
    order_tracking = TrackingInformation.query.filter_by(order_number=order_number,
                                                         order_detail_id=order_detail_id,
                                                         user_id=user_id).first()
    order_detail = OrderDetails.query.filter_by(order_number=order_number,
                                                id=order_detail_id,
                                                user_id=user_id).first()
    order = Orders.query.filter_by(order_number=order_number,
                                   user_id=user_id).first()
    return render_template("order_tracking.html", order_tracking=order_tracking, order_detail=order_detail, order=order)


@app.route("/order-details/<order_number>/<order_detail_id>/<order_id>/<product_id>/<product_identifier>/<user_id"
           ">/cancel-order/",
           methods=["GET", "POST"])
def cancel_order(order_detail_id, order_id, order_number, product_id, product_identifier, user_id):
    if request.method == "POST":
        order = Orders.query.filter_by(order_number=order_number, user_id=user_id).first()

        current_order_detail = OrderDetails.query.filter_by(
            id=order_detail_id,
            order_id=order_id,
            order_number=order_number,
            product_id=product_id,
            product_identifier=product_identifier,
            user_id=user_id).first()

        if request.form.get("cancel_purpose") == "order":
            if current_order_detail.order_status == "Being Prepared":
                cancelled = CancelledOrders(
                    order_number=order_number,
                    order_id=order_id,
                    order_detail_id=order_detail_id,
                    product_id=product_id,
                    product_identifier=product_identifier,
                    title=current_order_detail.title,
                    color=current_order_detail.color,
                    price=current_order_detail.price,
                    quantity=current_order_detail.quantity,
                    refunded_amount=round(float(current_order_detail.quantity * current_order_detail.price), 2),
                    main_img_path=current_order_detail.main_img_path,
                    cancel_date=current_date(),
                    user_id=current_user.id
                )
                current_order_detail.order_status = "Cancelled"
                order_detail_status_all = []
                # check all order details to see if every purchase has been cancelled
                order_details_all = OrderDetails.query.filter_by(order_number=order_number, user_id=user_id).all()
                for item in order_details_all:
                    order_detail_status_all.append(item.order_status)

                # if every purchase of the order number is cancelled, change the overall status to cancelled
                if all(element == order_detail_status_all[0] for element in order_detail_status_all):
                    order.shipment_status = "Cancelled"

                else:
                    order.shipment_status = "Partial Cancel"

                db.session.add(cancelled)
                db.session.commit()
                return redirect(request.referrer)
        else:
            return redirect(request.referrer)
    else:
        return redirect(request.referrer)


@app.route("/return_order/<order_number>/<order_det_id>/<product_identifier>/", methods=["GET", "POST"])
def return_order(order_number, order_det_id, product_identifier):
    if current_user.is_authenticated:
        if request.method == "POST":
            returned_product = Products.query.filter_by(product_identifier=product_identifier).first()
            if returned_product is None:
                returned_product = VariationProducts.query.filter_by(product_identifier=product_identifier).first()

            returned_product_details = OrderDetails.query.filter_by(id=order_det_id,
                                                                    order_number=order_number,
                                                                    product_identifier=product_identifier,
                                                                    user_id=current_user.id).first()

            order_detail_id = returned_product_details.id
            returned_quantity = request.form.get("returned_quantity")
            product_price = returned_product.price
            return_reason = request.form.get("return_reason")
            purchased_quantity = returned_product_details.quantity
            total_value = round(float(returned_quantity) * float(product_price), 2)
            order_returned = Returns(
                order_number=order_number,
                order_detail_id=order_detail_id,
                product_id=returned_product.id,
                product_identifier=returned_product.product_identifier,
                product_title=returned_product.title,
                product_color=returned_product.color,
                product_price=returned_product.price,
                returned_quantity=returned_quantity,
                purchased_quantity=purchased_quantity,
                total_value=total_value,
                return_reason=return_reason,
                return_date=current_date(),
                approve="Pending",
                main_img_path=returned_product.main_img_path,
                user_id=current_user.id,
            )
            returned_product_details.returned_quantity += int(returned_quantity)
            returned_product_details.order_status = "Return Opened"
            db.session.add(order_returned)
            db.session.commit()
            return redirect(url_for("profile"))


# cr = OrderDetails.query.filter_by(order_number=39934169469, id=1, user_id=2).first()
# cr.order_status = "Delivered"
# crt = TrackingInformation.query.filter_by(order_number=39934169469, order_detail_id=1, user_id=2).first()
# crt.shipment_status = "Delivered"
# db.session.commit()


@app.route("/cancel_return_request/<order_number>/<order_detail_id>/"
           "<order_id>/<product_id>/<returned_quantity>/<user_id>/", methods=["GET", "POST"])
def cancel_return_request(order_number, order_detail_id, order_id, product_id, returned_quantity, user_id):
    if current_user.is_authenticated:
        if request.form.get("cancel_purpose") == "return":
            current_order_detail = OrderDetails.query.filter_by(
                id=order_detail_id,
                order_number=order_number,
                order_id=order_id,
                product_id=product_id,
                user_id=user_id).first()

            current_tracking = TrackingInformation.query.filter_by(
                order_number=order_number,
                order_detail_id=order_detail_id,
                user_id=user_id).first()

            Returns.query.filter_by(order_number=order_number,
                                    order_detail_id=order_detail_id,
                                    product_id=product_id,
                                    user_id=user_id).delete()

            current_order_detail.order_status = "Delivered"
            current_order_detail.returned_quantity -= int(returned_quantity)

            current_tracking.shipment_status = "Delivered"
            db.session.commit()
            return redirect(request.referrer)


@app.route("/return_orders/", methods=["GET", "POST"])
def return_order_detail_page():
    user_returns = Returns.query.filter_by(user_id=current_user.id).all()
    user_order_details = OrderDetails.query.filter_by(user_id=current_user.id).all()
    return render_template("return_details.html", returns=user_returns, order_details=user_order_details)


# # # # # # # #  PRODUCT RELATED ROUTES / FUNCTIONS # # # # # # # #
@app.route("/products")
def products():
    p_products_all = Products.query.all()
    v_products_all = VariationProducts.query.all()
    products_all = []
    for p in p_products_all:
        products_all.append(p)
    for v in v_products_all:
        products_all.append(v)

    return render_template("products.html", products=products_all)


@app.route("/products", methods=["GET", "POST"])
def handle_user_filter():
    if request.method == "POST":
        minimum_price = 0
        maximum_price = 0

        if request.form["price_filter"] == "All-Prices":
            price_filter = "all"
        else:

            price_filter = request.form["price_filter"].split()
            minimum_price += float(price_filter[0])
            maximum_price += float(price_filter[1])

        if request.form["color_filter"] == "All-Colors":
            color_filter = "all"
        else:
            color_filter = request.form["color_filter"]

        requested_type = []
        # if all 3 filters selected with All Prices
        if price_filter == "all" and color_filter == "all":
            requested_type.append(Products.query.all())
            return render_template("products.html", products=requested_type[0])

        # if all filters are selected other than All Prices
        if price_filter != "all" and color_filter != "all":
            for p in Products.query.all():
                if minimum_price < p.price < maximum_price and \
                        color_filter in p.color.split():
                    requested_type.append(p)

        # if only 1 filter is selected other than All Prices
        elif price_filter == "all" and color_filter != "all":
            for p in Products.query.all():
                if color_filter in p.color.split():
                    requested_type.append(p)

        elif price_filter == "all" and color_filter != "all":
            for p in Products.query.all():
                if color_filter in p.color.split():
                    requested_type.append(p)

        elif price_filter != "all" and color_filter == "all":
            for p in Products.query.all():
                if minimum_price < p.price < maximum_price:
                    requested_type.append(p)

        # if 2 inputs are different from All Prices
        elif price_filter == "all" and color_filter != "all":
            for p in Products.query.all():
                if color_filter in p.color.split():
                    requested_type.append(p)

        elif price_filter != "all" and color_filter != "all":
            for p in Products.query.all():
                if minimum_price < p.price < maximum_price and color_filter in p.color.split():
                    requested_type.append(p)

        elif price_filter != "all" and color_filter == "all":
            for p in Products.query.all():
                if minimum_price < p.price < maximum_price:
                    requested_type.append(p)

        if len(requested_type) == 0:
            flash("Filter is not matching with any available products. We are showing you all the products right now.",
                  "filter_search")
            return render_template("products.html", products=Products.query.all())
        return render_template("products.html", products=requested_type)
    return redirect(request.referrer)


@app.route("/product/parent/<id>/<product_identifier>/")
def product(id, product_identifier):
    product_to_show = Products.query.filter_by(id=id, product_identifier=product_identifier).first()
    if product_to_show is None:
        return redirect(url_for("show_variation_product", id=id, product_identifier=product_identifier))

    color = product_to_show.color
    quantity = product_to_show.stock
    variations = VariationProducts.query.filter_by(parent_product_identifier=product_to_show.product_identifier).all()
    variation_dic = {}
    for var in variations:
        variation_dic[var] = var.color

    if current_user.is_authenticated:
        if not UserFav.query.filter_by(product_id=id,
                                       product_identifier=product_identifier,
                                       user_id=current_user.id).first() is None:
            fav_status = "Added"
            fav_id = UserFav.query.filter_by(product_id=id, user_id=current_user.id).first().id
            return render_template("product.html",
                                   product_to_show=product_to_show,
                                   parent_product=product_to_show,
                                   color=color,
                                   selected_color=product_to_show.color,
                                   var_color=variation_dic,
                                   stock=quantity,
                                   fav_status=fav_status,
                                   fav_id=fav_id,
                                   variations=variations
                                   )
        else:
            fav_status = "NotAdded"
            return render_template("product.html",
                                   product_to_show=product_to_show,
                                   parent_product=product_to_show,
                                   color=color,
                                   selected_color=product_to_show.color,
                                   var_color=variation_dic,
                                   stock=quantity,
                                   fav_status=fav_status,
                                   )
    else:
        return render_template("product.html",
                               product_to_show=product_to_show,
                               parent_product=product_to_show,
                               color=color,
                               selected_color=product_to_show.color,
                               var_color=variation_dic,
                               stock=quantity,
                               )


@app.route("/product/variation/<id>/<product_identifier>/", methods=["GET", "POST"])
def show_variation_product(id, product_identifier):
    variation_product = VariationProducts.query.filter_by(id=id, product_identifier=product_identifier).first()
    if variation_product is None:  # check if the product is deleted from db by admin
        return render_template("product_not_found.html")

    parent_product = Products.query.filter_by(product_identifier=variation_product.parent_product_identifier).first()

    color = parent_product.color
    quantity = variation_product.stock
    variations = VariationProducts.query.filter_by(parent_product_identifier=parent_product.product_identifier).all()
    variation_dic = {}
    for var in variations:
        variation_dic[var] = var.color

    selected_color = variation_product.color

    if current_user.is_authenticated:
        if not UserFav.query.filter_by(product_id=id,
                                       product_identifier=product_identifier,
                                       user_id=current_user.id).first() is None:
            fav_status = "Added"
            fav_id = UserFav.query.filter_by(product_id=id, user_id=current_user.id).first().id
            return render_template("product.html",
                                   product_to_show=variation_product,
                                   parent_product=parent_product,
                                   color=color,
                                   selected_color=selected_color,
                                   var_color=variation_dic,
                                   stock=quantity,
                                   fav_status=fav_status,
                                   fav_id=fav_id,
                                   variations=variations
                                   )
        else:
            fav_status = "NotAdded"
            return render_template("product.html",
                                   product_to_show=variation_product,
                                   parent_product=parent_product,
                                   color=color,
                                   selected_color=selected_color,
                                   var_color=variation_dic,
                                   stock=quantity,
                                   fav_status=fav_status,
                                   )
    else:
        return render_template("product.html",
                               product_to_show=variation_product,
                               parent_product=parent_product,
                               color=color,
                               selected_color=selected_color,
                               var_color=variation_dic,
                               stock=quantity,
                               )


# # # # # # #  LOG IN / REGISTER / LOG OUT ROUTES  # # # # # # # #

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email")
        admin = AdminUser.query.filter_by(email=email).first()
        if admin:
            password = request.form.get("password")
            if check_password_hash(admin.password, password):
                login_user(admin)
                return redirect(url_for("home"))
            else:
                return redirect(request.referrer)
        else:
            return redirect(request.referrer)
    return render_template("admin_login.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()
        if user:
            password = request.form.get("password")
            if check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for("home"))
            else:
                flash("incorrect password, please try again", "login")
        else:
            flash("wrong email, please try again", "login")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()
        if user:
            flash("email already exists, please log in", "register")
            return redirect(url_for("login"))
        else:
            if not request.form.get("gender") is None:
                password = request.form.get("password")
                password_repeat = request.form.get("password-repeat")
                if password == password_repeat:
                    pw_hash = generate_password_hash(
                        password=password,
                        method="pbkdf2:sha256",
                        salt_length=8
                    )
                    new_user = User(
                        name=request.form.get("name"),
                        surname=request.form.get("surname"),
                        birthdate=request.form.get("birthdate"),
                        gender=request.form.get("gender"),
                        phone_number_ext=request.form.get("phone_number_ext"),
                        phone_number=request.form.get("phone_number"),
                        email=request.form.get("email"),
                        password=pw_hash,
                    )
                    db.session.add(new_user)
                    db.session.commit()
                    login_user(new_user)
                    return redirect(url_for("home"))
                else:
                    flash("Password is not matching. Please try again.", "register")
                    return redirect(request.url)
            else:
                flash("Please choose a gender.", "register")
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


# # # # # # # # # # # # # # # # # # # # # # ----ADMIN RELATED----  # # # # # # # # # # # # # # # # # # # # # #

# # # # # # #  ADMIN ADD PRODUCT TO INVENTORY  # # # # # # # #
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# To make each filename unique incase user uploads files with duplicate names.
# Duplicate filenames cause problem when relocating the files, FileExists error.
def make_unique(string):
    uuid = uuid4().__str__()
    return f"{uuid}-{string}"


@app.route("/add_product", methods=["POST", "GET"])
@login_required
@admin_only
def add_product():
    global BASE_PATH
    if request.method == "POST":
        if 'img-files' not in request.files:
            flash('No file has been uploaded. Please upload images to continue.', "add_product_flash")
            return redirect(request.url)

        files = request.files.getlist('img-files')  # get multiple uploaded files

        if len(files) > 5:
            flash("You can only upload 5 image per product.", "add_product_flash")
            return redirect(request.url)

        for file in files:
            if file.filename == '':
                flash('You haven"t selected any images. Please select images.', "add_product_flash")
                return redirect(request.url)

            if file and allowed_file(file.filename):
                continue

            else:
                flash("Please DO NOT upload dangerous files.", "add_product_flash")
                return render_template("admin_add_product.html")

        title = request.form.get("title")
        description1 = request.form.get("description1")
        description2 = request.form.get("description2")
        description3 = request.form.get("description3")
        price = request.form.get("price")
        stock = request.form.get("stock")
        color = request.form.get("color")
        product_type = request.form.get("type")
        product_identifier = request.form.get("identifier")
        variation_type = request.form.get("variation")

        if variation_type == "Parent" or variation_type == "" or variation_type is None:
            variation_type = "Parent"
            if product_type == "wooden":
                BASE_PATH = f"static/images/wooden/" + product_identifier

            if product_type == "fiberglass":
                BASE_PATH = f"static/images/fiberglass/" + product_identifier

            if product_type == "metal":
                BASE_PATH = f"static/images/metal/" + product_identifier  # base path for new dir

            if product_type == "bamboo":
                BASE_PATH = f"static/images/bamboo/" + product_identifier

            new_dir = os.path.splitext(BASE_PATH)[0]  # removing extension before creating the new dir
            if os.path.exists(new_dir):  # check if there's a directory with the same name
                flash(f"Product Identifier '{product_identifier}' is not unique. Please try another.",
                      "add_product_flash")
            else:
                # USER PRODUCT INPUTS
                os.mkdir(new_dir)  # creating new dir for that specific product identifier / "keep it out of loop"
                product_dir_path = os.path.dirname(new_dir) + f"/{product_identifier}"  # catch new dir path
                main_img = ""
                second_img = ""
                third_img = ""
                fourth_img = ""
                fifth_img = ""
                for idx, file in enumerate(files):
                    original_filename = secure_filename(file.filename)
                    # make filenames unique incase user uploads files with duplicate names.
                    # otherwise it will cause a FileExists error later when you relocate the images to new file.
                    unique_filename = make_unique(original_filename)
                    if idx == 0:
                        main_img = product_dir_path + "/" + unique_filename
                    if idx == 1:
                        second_img = product_dir_path + "/" + unique_filename
                    if idx == 2:
                        third_img = product_dir_path + "/" + unique_filename
                    if idx == 3:
                        fourth_img = product_dir_path + "/" + unique_filename
                    if idx == 4:
                        fifth_img = product_dir_path + "/" + unique_filename
                    filename = unique_filename  # get the filename for each uploaded file
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))  # save the uploaded files to folder
                    uploaded_images = [f for f in os.listdir(UPLOAD_FOLDER)]
                    for image in uploaded_images:
                        if image.endswith('.jpg') or \
                                image.endswith('.png') or \
                                image.endswith('.jpeg') or \
                                image.endswith('.PNG'):
                            os.rename(f"static/images/{image}", f"{new_dir}/{image}")  # move img to new dir
                # Add product to db
                new_product = Products(
                    product_identifier=product_identifier,
                    variation_type=variation_type,
                    child_variation_identifiers="None",
                    title=title,
                    description1=description1,
                    description2=description2,
                    description3=description3,
                    price=price,
                    stock=stock,
                    color=color,
                    product_type=product_type,
                    file_path=product_dir_path,
                    main_img_path=main_img,
                    second_img_path=second_img,
                    third_img_path=third_img,
                    fourth_img_path=fourth_img,
                    fifth_img_path=fifth_img
                )
                try:
                    db.session.add(new_product)
                    db.session.commit()
                    flash("Product has been added!", "add_product_flash")
                    return redirect(url_for("add_product"))
                except sqlalchemy.exc.OperationalError:
                    flash("Somethings wrong, please try again in a few minutes.", "add_product_flash")
                    print("database is probably locked, check it")
                    return redirect(url_for("add_product"))

        # add variation product
        elif variation_type == "Child":
            parent_product_identifier = request.form.get("parent_product_identifier")
            parent_product = Products.query.filter_by(product_identifier=parent_product_identifier).first()
            parent_base_path = parent_product.file_path

            child_product_identifier = request.form.get("identifier")
            new_path_child = parent_base_path + "/" + child_product_identifier
            os.mkdir(new_path_child)
            main_img = ""
            second_img = ""
            third_img = ""
            fourth_img = ""
            fifth_img = ""
            for idx, file in enumerate(files):
                original_filename = secure_filename(file.filename)
                # make filenames unique incase user uploads files with duplicate names.
                # otherwise it will cause a FileExists error later when you relocate the images to new file.
                unique_filename = make_unique(original_filename)
                if idx == 0:
                    main_img = new_path_child + "/" + unique_filename
                if idx == 1:
                    second_img = new_path_child + "/" + unique_filename
                if idx == 2:
                    third_img = new_path_child + "/" + unique_filename
                if idx == 3:
                    fourth_img = new_path_child + "/" + unique_filename
                if idx == 4:
                    fifth_img = new_path_child + "/" + unique_filename
                filename = unique_filename  # get the filename for each uploaded file
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))  # save the uploaded files to folder
                uploaded_images = [f for f in os.listdir(UPLOAD_FOLDER)]
                for image in uploaded_images:
                    if image.endswith('.jpg') or \
                            image.endswith('.png') or \
                            image.endswith('.jpeg') or \
                            image.endswith('.PNG'):
                        os.rename(f"static/images/{image}", f"{new_path_child}/{image}")  # move img to new dir
            # Add product to db
            new_product = VariationProducts(
                product_identifier=child_product_identifier,
                variation_type=variation_type,
                parent_product_id=parent_product.id,
                parent_product_identifier=parent_product.product_identifier,
                title=title,
                description1=description1,
                description2=description2,
                description3=description3,
                price=price,
                stock=stock,
                color=color,
                product_type=product_type,
                file_path=new_path_child,
                main_img_path=main_img,
                second_img_path=second_img,
                third_img_path=third_img,
                fourth_img_path=fourth_img,
                fifth_img_path=fifth_img
            )

            try:
                db.session.add(new_product)
                parent_obj = Products.query.filter_by(product_identifier=parent_product.product_identifier).first()
                parent_base = Products.query.filter_by(product_identifier=parent_product.product_identifier)

                if parent_obj.child_variation_identifiers == "None" or parent_obj.child_variation_identifiers == "":
                    parent_base.update({Products.child_variation_identifiers: ""})

                    child_var_list = parent_obj.child_variation_identifiers.split()
                    child_var_list.append(new_product.product_identifier)
                    child_var_str = ''.join(str(child) for child in child_var_list)
                    parent_base.update({Products.child_variation_identifiers: child_var_str + " "})

                else:
                    child_var_list = parent_obj.child_variation_identifiers.split()
                    child_var_list.append(new_product.product_identifier)
                    child_var_str = ''.join(str(child) for child in child_var_list)
                    parent_base.update({Products.child_variation_identifiers: child_var_str + " "})

                db.session.commit()
                flash("Product has been added!", "add_product_flash")
                return redirect(url_for("add_product"))
            except sqlalchemy.exc.OperationalError:
                flash("Somethings wrong, please try again in a few minutes.", "add_product_flash")
                print("database is probably locked, check it")
                return redirect(url_for("add_product"))
    return render_template("admin_add_product.html")


# # # # # # #  ADMIN INVENTORY ROUTES  # # # # # # # #
@app.route("/admin/inventory/search_by_title/", methods=["GET", "POST"])
def search_inventory():
    if request.method == "POST":
        input_text = request.form.get("input_text")
        parent_products = Products.query.all()
        variation_products = VariationProducts.query.all()
        combined = parent_products + variation_products

        searched_list = []
        for p in combined:
            if input_text.lower() in p.title.lower():
                searched_list.append(p)

        return render_template("admin_inventory.html", products=searched_list)
    return redirect(url_for("inventory"))


@app.route("/admin/inventory/filter/", methods=["GET", "POST"])
def inventory_filter():
    filter_value = request.form.get("filter_by")
    return redirect(url_for("inventory", filter_by=filter_value))


@app.route("/admin/inventory/filter/<filter_by>", methods=["GET", "POST"])
@login_required
@admin_only
def inventory(filter_by):
    products_all = []
    parent_products = Products.query.all()
    variation_products = VariationProducts.query.all()

    for item in parent_products:
        products_all.append(item)
    for item in variation_products:
        products_all.append(item)

    if filter_by == "None":
        return render_template("admin_inventory.html", products=products_all)

    if filter_by == "filter_price_desc":
        for i in range(0, len(products_all)):
            for j in range(i + 1, len(products_all)):
                if products_all[i].price < products_all[j].price:
                    temp = products_all[i]
                    products_all[i] = products_all[j]
                    products_all[j] = temp

    if filter_by == "filter_price_asc":
        for i in range(0, len(products_all)):
            for j in range(i + 1, len(products_all)):
                if products_all[i].price > products_all[j].price:
                    temp = products_all[i]
                    products_all[i] = products_all[j]
                    products_all[j] = temp

    if filter_by == "filter_stock_desc":
        for i in range(0, len(products_all)):
            for j in range(i + 1, len(products_all)):
                if products_all[i].stock < products_all[j].stock:
                    temp = products_all[i]
                    products_all[i] = products_all[j]
                    products_all[j] = temp

    if filter_by == "filter_stock_asc":
        for i in range(0, len(products_all)):
            for j in range(i + 1, len(products_all)):
                if products_all[i].stock > products_all[j].stock:
                    temp = products_all[i]
                    products_all[i] = products_all[j]
                    products_all[j] = temp

    if filter_by == "filter_identifier":
        assign_dict = {}
        for p in products_all:
            assign_dict[p] = p.product_identifier

        sorted_dict = dict(sorted(assign_dict.items(), key=lambda item: item[1]))
        products_all.clear()

        for key, value in sorted_dict.items():
            products_all.append(key)

        return render_template("admin_inventory.html", products=products_all)

    if filter_by == "filter_category":
        assign_dict = {}
        for p in products_all:
            assign_dict[p] = p.product_type

        sorted_dict = dict(sorted(assign_dict.items(), key=lambda item: item[1]))
        products_all.clear()

        for key, value in sorted_dict.items():
            products_all.append(key)

    return render_template("admin_inventory.html", products=products_all)


@app.route("/admin/inventory/update", methods=["GET", "POST"])
@login_required
@admin_only
def update_inventory():
    if request.method == "POST":
        product_identifier = request.form.get("product_identifier")
        product_id = request.form.get("product_id")

        current_product = Products.query.filter_by(id=product_id, product_identifier=product_identifier).first()
        if current_product is None:
            current_product = VariationProducts.query.filter_by(id=product_id,
                                                                product_identifier=product_identifier).first()

        carts = UserCart.query.all()
        favs = UserFav.query.all()

        action = request.form.get("action")
        if action == "update_price_stock":
            price = request.form.get("price")
            stock = request.form.get("stock")
            if price:
                # change current product price
                current_product.price = float(price)

                # change the price on all carts
                for item in carts:
                    if item.product_id == current_product.id and item.product_identifier == current_product.product_identifier:
                        item.price = float(price)
                        item.total_price = item.quantity * float(price)

                # change the price on all favourites
                for item in favs:
                    if item.product_id == current_product.id and item.product_identifier == current_product.product_identifier:
                        item.price = float(price)
                        item.total_price = item.quantity * float(price)

                db.session.commit()
            if stock:
                current_product.stock = int(stock)
                db.session.commit()

            return redirect(url_for("inventory", filter_by="None"))

        if action == "update_details":
            new_title = request.form.get("product_title").title()
            new_descr1 = request.form.get("descr1")
            new_descr2 = request.form.get("descr2")
            new_descr3 = request.form.get("descr3")

            # title
            if new_title != "":
                current_product.title = new_title
                # change the title on all carts and favourites
                for item in carts:
                    if item.product_id == current_product.id and \
                            item.product_identifier == current_product.product_identifier:
                        item.title = new_title

                for item in favs:
                    if item.product_id == current_product.id and \
                            item.product_identifier == current_product.product_identifier:
                        if item.product_id == current_product.id and \
                                item.product_identifier == current_product.product_identifier:
                            item.title = new_title

            # description1
            if new_descr1 != "":
                current_product.description1 = new_descr1

            # description2
            if new_descr2 != "":
                current_product.description2 = new_descr2

            # description3
            if new_descr3 != "":
                current_product.description3 = new_descr3

            db.session.commit()
            return redirect(url_for("inventory", filter_by="None"))

        elif action == "delete":
            if Products.query.filter_by(id=product_id, product_identifier=product_identifier).first() is not None:
                Products.query.filter_by(id=product_id, product_identifier=product_identifier).delete()
                db.session.commit()
            else:
                VariationProducts.query.filter_by(id=product_id, product_identifier=product_identifier).delete()
                db.session.commit()

    return redirect(url_for("inventory", filter_by="None"))


@app.route("/admin/orders_filter/", methods=["GET", "POST"])
@admin_only
def orders_filter():
    filter_value = request.form.get("filter_by")
    return redirect(url_for("admin_orders_all", filter_by=filter_value))


@app.route("/admin/orders_search/", methods=["GET", "POST"])
def admin_search_order():
    search_value = request.form.get("input_text")
    print(search_value)
    search_value += " search"
    return redirect(url_for("admin_orders_all", filter_by=search_value))


@app.route("/admin/orders_all/filter/<filter_by>/", methods=["GET", "POST"])
def admin_orders_all(filter_by):
    orders_all = Orders.query.all()
    if filter_by == "None" or filter_by == "date_ascending" or filter_by == "all_orders":
        print(orders_all)
        return render_template("admin_orders.html", orders=orders_all)

    if filter_by == "date_descending":
        orders_all.reverse()
        print(orders_all)
        return render_template("admin_orders.html", orders=orders_all)

    if filter_by.split()[1] == "search":
        order_number = int(filter_by.split()[0])

        # since you will loop through in the admin_orders page, make it a list
        # because this will return single object
        order_to_show = [Orders.query.filter_by(order_number=order_number).first()]
        return render_template("admin_orders.html", orders=order_to_show)


@app.route("/admin/order/specific/<order_number>/<user_id>/", methods=["GET"])
@admin_only
def admin_show_order(order_number, user_id):
    current_order = Orders.query.filter_by(order_number=order_number, user_id=user_id).first()
    order_detail = OrderDetails.query.filter_by(order_number=order_number, user_id=user_id).all()
    detail_list = [det for det in order_detail]

    total_cost = 0
    total_order_quantity = 0
    for purchase in detail_list:
        total_cost += purchase.total_price
        total_order_quantity += purchase.quantity

    delivery_address = UserAddresses.query.filter_by(id=current_order.delivery_address_ids,
                                                     user_id=current_order.user_id).first()
    billing_address = UserBillingAddresses.query.filter_by(id=current_order.billing_address_ids,
                                                           user_id=current_order.user_id).first()

    return render_template("admin_order_detail.html",
                           order_detail=detail_list,
                           order=current_order,
                           total_cost=total_cost,
                           total_quantity=total_order_quantity,
                           delivery_address=delivery_address,
                           billing_address=billing_address,
                           )


@app.route("/admin/order/create_shipment/<order_number>/<order_detail_id>/<user_id>/", methods=["GET", "POST"])
@admin_only
def create_shipment(order_number, order_detail_id, user_id):
    if request.method == "POST":
        current_tracking = TrackingInformation.query.filter_by(order_number=order_number,
                                                               order_detail_id=order_detail_id, user_id=user_id)
        current_order_detail = OrderDetails.query.filter_by(order_number=order_number,
                                                            id=order_detail_id,
                                                            user_id=user_id).first()

        current_order = Orders.query.filter_by(order_number=order_number, user_id=user_id).first()
        current_order_detail_list = OrderDetails.query.filter_by(order_number=order_number,
                                                                 user_id=user_id).all()

        tracking_number = str(request.form.get("tracking_no"))
        company = str(request.form.get("company"))
        exp_delivery_date = str(request.form.get("date"))
        status = request.form.get("status")

        current_tracking.update({TrackingInformation.tracking_number: tracking_number})
        current_tracking.update({TrackingInformation.shipping_company: company})
        current_tracking.update({TrackingInformation.expected_delivery_date: exp_delivery_date})
        current_tracking.update({TrackingInformation.shipment_status: status})

        current_order_detail.order_status = status

        status_all = []
        for detail in current_order_detail_list:
            status_all.append(detail.order_status)

        if "Being Prepared" in status_all and "Shipped" in status_all:
            current_order.shipment_status = "Partial Shipped"

        if all(element == status_all[0] for element in status_all):  # check if each order is shipped
            current_order.shipment_status = "Shipped"

        db.session.commit()

        return redirect(request.referrer)


@app.route("/admin/order_tracking/<order_number>/<order_detail_id>/<user_id>/", methods=["GET", "POST"])
@admin_only
def admin_order_tracking_page(order_number, order_detail_id, user_id):
    order_tracking = TrackingInformation.query.filter_by(order_number=order_number,
                                                         order_detail_id=order_detail_id,
                                                         user_id=user_id).first()
    order_detail = OrderDetails.query.filter_by(order_number=order_number,
                                                id=order_detail_id,
                                                user_id=user_id).first()
    order = Orders.query.filter_by(order_number=order_number,
                                   user_id=user_id).first()
    return render_template("admin_order_tracking.html", order_tracking=order_tracking, order_detail=order_detail,
                           order=order)


@app.route("/admin/returns/", methods=["GET", "POST"])
@admin_only
def admin_return_requests():
    returns_all = Returns.query.all()
    return render_template("admin_return_page.html", returns=returns_all)


@app.route("/admin/return_requests/<action>/<order_number>/<order_detail_id>/<user_id>/", methods=["GET", "POST"])
@admin_only
def handle_return_request(action, order_number, order_detail_id, user_id):
    if request.method == "POST":
        current_order_detail = OrderDetails.query.filter_by(order_number=order_number,
                                                            id=order_detail_id,
                                                            user_id=user_id).first()

        current_return = Returns.query.filter_by(order_number=order_number,
                                                 order_detail_id=order_detail_id,
                                                 user_id=user_id).first()
        if action == "Accept":
            shipment_number = request.form.get("shipment_number")
            company = request.form.get("company")

            current_order_detail.order_status = f"Accepted {shipment_number} {company}"
            current_return.approve = f"Accepted {shipment_number} {company}"
            db.session.commit()

        elif action == "Deny":
            reason = request.form.get("deny_reason")

            current_order_detail.order_status = f"Deny {reason}"
            current_return.approve = f"Deny {reason}"
            db.session.commit()
        return redirect(request.referrer)


@app.route("/admin/orders/cancelled", methods=["GET"])
def admin_cancelled_orders():
    cancelled_orders = CancelledOrders.query.all()
    return render_template("admin_cancelled_orders.html", orders=cancelled_orders)

@app.route("/test", methods=["GET"])
def test():
    return render_template("test.html")


if __name__ == "__main__":
    app.run(port=5000, debug=True, host="localhost")
