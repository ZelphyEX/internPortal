"""Kiểm tra chuỗi migration chỉ có ĐÚNG MỘT head. Chạy trong CI trước khi build.

Vì sao cần: `Dockerfile` chạy `alembic upgrade head && ... && uvicorn`. Nếu có hai
migration cùng `down_revision` (hai người tạo song song), Alembic báo lỗi
"Multiple head revisions are present" và **không chạy gì cả** -> `&&` đứt -> uvicorn
không khởi động -> Cloud Run báo "container failed to start and listen on port 8080".
Thông báo đó không hề nhắc tới migration nên rất mất thời gian truy nguyên.

Script cố tình KHÔNG import alembic/sqlalchemy và KHÔNG kết nối DB — chỉ đọc file,
để chạy được ở bước CI chưa cài dependency nào.

Cách sửa khi script báo lỗi: chọn một nhánh, sửa `down_revision` của nó trỏ vào
revision của nhánh kia để thành một chuỗi thẳng.

Dùng:
    python -m scripts.check_migration_heads
"""
import pathlib
import re
import sys

VERSIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "alembic" / "versions"

_REVISION = re.compile(r"^revision(?::\s*str)?\s*=\s*['\"]([^'\"]+)['\"]", re.M)
_DOWN = re.compile(
    r"^down_revision(?::\s*[^=]+)?\s*=\s*(?:['\"]([^'\"]+)['\"]|None)", re.M
)


def main() -> int:
    revisions: dict[str, str] = {}   # revision -> tên file
    parents: dict[str, str] = {}     # revision -> down_revision

    for path in sorted(VERSIONS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        rev_match = _REVISION.search(text)
        if rev_match is None:
            continue
        rev = rev_match.group(1)
        if rev in revisions:
            print(
                f"LOI: revision id '{rev}' bi trung o {revisions[rev]} va {path.name}"
            )
            return 1
        revisions[rev] = path.name
        down_match = _DOWN.search(text)
        if down_match and down_match.group(1):
            parents[rev] = down_match.group(1)

    if not revisions:
        print("Khong tim thay migration nao — bo qua.")
        return 0

    # down_revision trỏ tới revision không tồn tại -> Alembic cũng sẽ chết.
    for rev, down in parents.items():
        if down not in revisions:
            print(
                f"LOI: {revisions[rev]} co down_revision='{down}' nhung khong co "
                "migration nao mang revision do."
            )
            return 1

    referenced = set(parents.values())
    heads = sorted(r for r in revisions if r not in referenced)

    if len(heads) == 1:
        print(f"OK: 1 head ({heads[0]} — {revisions[heads[0]]}), {len(revisions)} migration.")
        return 0

    print(f"LOI: co {len(heads)} head, Alembic se tu choi chay `upgrade head`:")
    for head in heads:
        print(f"  - {head}  ({revisions[head]})")
    print(
        "\nSua: chon mot nhanh, doi `down_revision` cua no tro vao revision cua "
        "nhanh kia de thanh mot chuoi thang."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
