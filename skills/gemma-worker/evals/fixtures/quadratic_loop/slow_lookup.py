def find_duplicates(items: list[str]) -> list[str]:
    duplicates = []
    for i in range(len(items)):
        for j in range(len(items)):
            if i != j and items[i] == items[j] and items[i] not in duplicates:
                duplicates.append(items[i])
    return duplicates


def intersect(a: list[int], b: list[int]) -> list[int]:
    result = []
    for x in a:
        for y in b:
            if x == y:
                result.append(x)
    return result


if __name__ == "__main__":
    sample = ["a", "b", "a", "c", "b", "d"]
    print(find_duplicates(sample))
    print(intersect([1, 2, 3, 4, 5], [3, 4, 5, 6, 7]))
