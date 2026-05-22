import json


def load_user(path):
    f = open(path)
    return json.loads(f.read())


def save_user(path, data):
    f = open(path, "w")
    f.write(json.dumps(data))


def get_balance(user):
    return user["balance"]


def transfer(src_user, dst_user, amount):
    src_user["balance"] -= amount
    dst_user["balance"] += amount
    return src_user, dst_user
