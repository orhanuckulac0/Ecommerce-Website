from datetime import datetime
from random import randint
from flask import session
from db_app import MY_EMAIL, MY_EMAIL_PASSWORD
import smtplib


def send_verification(email: str, verification_code: int):
    my_email = MY_EMAIL
    password = MY_EMAIL_PASSWORD

    with smtplib.SMTP("smtp.gmail.com", 587) as connection:  # creating an object of smtp, add 587 to prevent error
        connection.starttls()  # tls means Transport Layer Security,  way of securing our connection to our email server
        connection.login(user=my_email, password=password)
        connection.sendmail(
            from_addr=my_email,
            to_addrs=email,
            msg=f"Subject:Hello\n\n Please use this verification code to get a new password. \n\n {verification_code}"
        )


def current_date():
    date_time = datetime.now()
    date = date_time.strftime("%d/%m/%Y")
    now = datetime.now()
    time = now.strftime("%H:%M:%S")
    date = date + " " + time
    return date


# send this via email
def generate_random_code():
    digit = 6
    range_start = 10 ** (digit - 1)
    range_end = (10 ** digit) - 1
    generated_code = randint(range_start, range_end)
    session["code"] = generated_code
    return True


def order_num():
    digit = 10
    range_start = 10 ** (digit - 1)
    range_end = (10 ** digit) - 1
    generated_code = str(randint(range_start, range_end))
    first_index_num = randint(0, 7)
    random_index = randint(1, 9)
    random_index_num = randint(0, 7)

    nums = []
    for num in generated_code:
        nums.append(num)

    for idx, num in enumerate(nums):
        if idx == 0:
            nums[idx] = str(first_index_num)
        if idx == random_index:
            nums[idx] = str(random_index_num)

    changed_num = ""
    for number in nums:
        changed_num += number

    digit_new = 4
    range_start_new = 2 ** (digit_new - 1)
    range_end_new = (2 ** digit_new) - 1
    generated_code_new = str(randint(range_start_new, range_end_new))
    final_order_num = changed_num + generated_code_new
    print(int(final_order_num))
    return int(final_order_num)
