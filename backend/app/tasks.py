import uuid
import json
import time
from datetime import datetime
from celery.utils.log import get_task_logger
from .celery_app import celery
import whois
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from sqlalchemy.orm import Session
from .models import AnalysisResult
from .database import SessionLocal
from .config import SELENIUM_URL

logger = get_task_logger(__name__)

HEURISTIC_KEYWORDS = [
    "login", "verify", "account", "bank", "secure", "update", "password", "confirm", "click", "urgent"
]

def compute_heuristic_score(text: str) -> dict:
    text_lower = text.lower()
    found = [k for k in HEURISTIC_KEYWORDS if k in text_lower]
    score = min(40, len(found) * 8)  # up to 40 points
    return {"found_keywords": found, "score": score}

def domain_age_days(domain: str):
    try:
        w = whois.whois(domain)
        cd = w.creation_date
        if isinstance(cd, list):
            cd = cd[0]
        if cd is None:
            return None
        delta = (datetime.utcnow() - cd).days
        return delta
    except Exception:
        return None

def selenium_check(url: str) -> dict:
    result = {"success": False, "has_password_field": False, "title": None, "screenshot_path": None, "error": None}
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    try:
        driver = webdriver.Remote(command_executor=SELENIUM_URL, options=options)
        driver.set_page_load_timeout(30)
        driver.get(url)
        time.sleep(2)
        title = driver.title
        result["title"] = title
        inputs = driver.find_elements(By.XPATH, "//input[@type='password']")
        result["has_password_field"] = len(inputs) > 0
        screenshot_path = f"/tmp/{uuid.uuid4().hex}.png"
        driver.save_screenshot(screenshot_path)
        result["screenshot_path"] = screenshot_path
        result["success"] = True
        driver.quit()
    except WebDriverException as e:
        result["error"] = str(e)
    except Exception as e:
        result["error"] = str(e)
    return result

@celery.task(bind=True)
def analyze_url_task(self, url: str):
    task_id = self.request.id
    logger.info("Starting analysis for %s", url)

    db: Session = SessionLocal()
    details = {}
    final_score = 0
    row = None

    try:
        row = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.task_id == task_id)
            .first()
        )
        if row:
            row.url = url
            row.status = "RUNNING"
            row.risk_score = None
            row.details = {}
        else:
            row = AnalysisResult(
                task_id=task_id,
                url=url,
                status="RUNNING",
                risk_score=None,
                details={},
            )
            db.add(row)
        db.commit()
        db.refresh(row)

        from urllib.parse import urlparse

        hostname = ""
        path = ""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
            path = parsed.path or ""
        except Exception as e:
            details["parse_error"] = str(e)

        try:
            heur = compute_heuristic_score(f"{hostname} {path}")
            details["heuristic"] = heur
            final_score += heur["score"]
        except Exception as e:
            details["heuristic_error"] = str(e)

        try:
            dots = hostname.count(".")
            subdomain_flag = 0
            if dots >= 3:
                subdomain_flag = 10
            if hostname.startswith("www.") and "login" in hostname:
                subdomain_flag += 10
            details["subdomain_check"] = {"dots": dots, "score": subdomain_flag}
            final_score += subdomain_flag
        except Exception as e:
            details["subdomain_error"] = str(e)

        try:
            dom = hostname
            age_days = domain_age_days(dom)
            if age_days is None:
                age_score = 20
            elif age_days < 30:
                age_score = 30
            elif age_days < 365:
                age_score = 15
            else:
                age_score = 0
            details["domain_age_days"] = age_days
            details["domain_age_score"] = age_score
            final_score += age_score
        except Exception as e:
            details["domain_age_error"] = str(e)

        try:
            sel = selenium_check(url)
            details["selenium"] = sel
            if sel.get("has_password_field"):
                final_score += 30
        except Exception as e:
            details["selenium_error"] = str(e)

        final_score = max(0, min(100, int(final_score)))

        row.status = "COMPLETED"
        row.risk_score = final_score
        row.details = details
        db.add(row)
        db.commit()
        db.refresh(row)

        logger.info("Finished %s -> score %s", url, final_score)
        return {"task_id": task_id, "url": url, "risk_score": final_score, "details": details}
    except Exception as exc:
        logger.exception("Analysis failed for %s: %s", url, exc)
        if row:
            row.status = "FAILED"
            row.risk_score = None
            row.details = {**details, "task_error": str(exc)}
            db.add(row)
            db.commit()
        raise
    finally:
        db.close()
