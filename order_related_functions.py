from db_app import db, Orders, TrackingInformation, UserAddresses, UserBillingAddresses, OrderDetails, Products,\
    VariationProducts


def create_order_tracking(order_number, order_detail_id, user_id):
    """Temporary tracking information for orders just being processed"""
    status_being_prepared = "Being Prepared"
    # # # for delivery address info:
    current_order = Orders.query.filter_by(order_number=order_number, user_id=user_id).first()

    delivery_id = current_order.delivery_address_ids
    billing_id = current_order.billing_address_ids

    user_delivery = UserAddresses.query.filter_by(id=delivery_id, user_id=user_id).first()
    user_billing = UserBillingAddresses.query.filter_by(id=billing_id, user_id=user_id).first()

    delivery_address = user_delivery.address_line + " " + user_delivery.city + " " + user_delivery.state + " " \
                       + user_delivery.postal_code + " " + user_delivery.country
    billing_address = user_billing.address_line + " " + user_billing.city + " " + user_billing.state + " " \
                      + user_billing.postal_code + " " + user_billing.country
    # # #

    current_tracking = TrackingInformation.query.filter_by(order_number=order_number,
                                                           order_detail_id=order_detail_id,
                                                           user_id=user_id).first()
    order_detail = OrderDetails.query.filter_by(id=order_detail_id, order_number=order_number, user_id=user_id).first()

    # if there are no current tracking information for this product, make it Being Prepared and add to db:
    if current_tracking is None:
        update_tracking = TrackingInformation(
            order_number=order_number,
            order_detail_id=order_detail_id,
            tracking_number="Will be added",
            shipping_company="Will be added",
            expected_delivery_date="Will be added",
            shipment_status=status_being_prepared,
            receiver_name=user_delivery.name + " " + user_delivery.surname,
            receiver_contact_number=user_delivery.phone_number_ext + " " + user_delivery.phone_number,
            delivery_address=delivery_address,
            billing_address=billing_address,
            user_id=user_id
        )
        db.session.add(update_tracking)
        # change order status on order detail db
        order_detail.order_status = status_being_prepared
        db.session.commit()


def add_order_details(cart_items, order_number, user_id):
    current_order = Orders.query.filter_by(order_number=order_number, user_id=user_id).first()
    for item in cart_items:
        order_details = OrderDetails(
            order_number=order_number,
            product_id=item.product_id,
            order_id=current_order.id,
            product_identifier=item.product_identifier,
            title=item.title,
            color=item.color,
            price=item.price,
            quantity=item.quantity,
            total_price=item.total_price,
            order_status="Being Prepared",
            returned_quantity=0,
            main_img_path=item.main_img_path,
            user_id=user_id
        )
        db.session.add(order_details)
        # UserCart.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()

        # create order tracking for each item purchased
        create_order_tracking(order_number, order_detail_id=order_details.id, user_id=user_id)

        # subtract purchased quantity from product stock
        current_product = Products.query.filter_by(id=item.product_id,
                                                   product_identifier=item.product_identifier).first()
        if current_product is None:
            current_product = VariationProducts.query.filter_by(id=item.product_id,
                                                                product_identifier=item.product_identifier).first()
        current_product.stock -= item.quantity
        db.session.commit()
