import os
import logging
from contextlib import contextmanager
from urllib.parse import urlparse

import psycopg2
import requests
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for, abort

from page_analyzer import content, db
from page_analyzer.validator import validate

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
TIMEOUT = int(os.getenv('TIMEOUT'))
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')


@contextmanager
def connect(bd_url):
    try:
        connection = psycopg2.connect(bd_url)
        yield connection
    except Exception:
        if connection:
            connection.rollback()
        raise
    else:
        if connection:
            connection.commit()
    finally:
        if connection:
            connection.close()


@app.errorhandler(404)
def server_error(e):
    logging.error('Error: %s', e)
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error_global(e):
    logging.error('Error: %s', e)
    return render_template('500.html'), 500


@app.route('/')
def index():
    return render_template('index.html')


@app.get('/urls')
def urls_lists():
    with connect(DATABASE_URL) as conn:
        url_checks = db.get_all_url_checks(conn)
    return render_template(
        '/urls.html',
        urls=url_checks
    )


@app.post('/urls')
def urls_add():
    url_name = request.form.get('url')
    errors = validate(url_name)
    if errors:
        return render_template(
            'index.html',
            errors=errors,
        ), 422
    url_parsed = urlparse(url_name)
    url_name = url_parsed.scheme + '://' + url_parsed.netloc
    with connect(DATABASE_URL) as conn:
        url_id = db.get_url_by_name(conn, url_name)
        if url_id:
            flash('Страница уже существует', 'info')
            return redirect(url_for('url_info', id=url_id[0]))
        url_id = db.create_url(conn, url_name)
    flash('Страница успешно добавлена', 'success')
    return redirect(url_for('url_info', id=url_id))


@app.route('/urls/<id>')
def url_info(id):
    with connect(DATABASE_URL) as conn:
        url = db.get_url_by_id(conn, id)
        if not url:
            abort(404)
        name = url.name
        created_at = url.created_at
        url_checks = db.get_checks_by_url_id(conn, id)
    return render_template(
        'urls_id.html',
        id=id,
        name=name,
        created_at=created_at,
        checks=url_checks
    )


@app.route('/urls/<id>/checks', methods=['POST'])
def url_check(id):
    with connect(DATABASE_URL) as conn:
        url = db.get_url_by_id(conn, id)
        if not url:
            abort(404)
        name = url.name
        created_at = url.created_at
        try:
            request = requests.get(name, timeout=TIMEOUT)
            request.raise_for_status()
        except requests.RequestException:
            flash('Произошла ошибка при проверке', 'error')
            return redirect(url_for('url_info', id=id))
        code = request.status_code
        h1, title, description = content.get_seo_data_from_html(request.text)
        db.create_check(conn, id, code, h1, title, description)
        checks = db.get_check_by_url_id(conn, id)
    flash('Страница успешно проверена', 'success')
    # redirect(url_for('url_info', id=id))
    return render_template(
        'urls_id.html',
        id=id,
        name=name,
        created_at=created_at,
        checks=checks
    )
