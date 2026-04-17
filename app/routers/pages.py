from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "page": "index"})


@router.get("/compare", response_class=HTMLResponse)
def compare(request: Request):
    return templates.TemplateResponse("compare.html", {"request": request, "page": "compare"})


@router.get("/evals", response_class=HTMLResponse)
def evals(request: Request):
    return templates.TemplateResponse("evals.html", {"request": request, "page": "evals"})
