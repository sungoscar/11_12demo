from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from auth_utils import render_page, require_role


def editor_required(request: Request):
    return require_role(request, "editor")


router = APIRouter(dependencies=[Depends(editor_required)])


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return render_page(request, "role_home.html", role_title="編輯首頁",
                       description="歡迎來到編輯專區。審查功能將於後續階段開放。")
