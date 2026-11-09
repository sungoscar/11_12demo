from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from auth_utils import render_page, require_role


def author_required(request: Request):
    return require_role(request, "author")


router = APIRouter(dependencies=[Depends(author_required)])


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return render_page(request, "role_home.html", role_title="作者首頁",
                       description="歡迎來到作者專區。投稿功能將於後續階段開放。")
