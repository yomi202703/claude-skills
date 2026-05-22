def used_helper(x):
    return x + 1


def unused_orphan_xyz():
    return 42


print(used_helper(1))
