from __future__ import annotations
from flask import render_template, jsonify, request
from flask.typing import ResponseReturnValue
from . import settings
from app.services.bulk_format_generator import BulkFormatGeneratorService
from app.services.logger import log_error
import traceback


@settings.route('/')
def index() -> ResponseReturnValue:
    return render_template('settings.html')


@settings.route('/generate-missing-epubs', methods=['POST'])
def generate_missing_epubs() -> ResponseReturnValue:
    try:
        service = BulkFormatGeneratorService()
        result = service.generate_missing_epubs()
        return jsonify(result)
    except Exception as e:
        error_msg = f"Error generating missing EPUBs: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while generating EPUBs"
        }), 500


@settings.route('/generate-missing-html', methods=['POST'])
def generate_missing_html() -> ResponseReturnValue:
    try:
        service = BulkFormatGeneratorService()
        result = service.generate_missing_html()
        return jsonify(result)
    except Exception as e:
        error_msg = f"Error generating missing HTML: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while generating HTML"
        }), 500


@settings.route('/generate-all-missing-formats', methods=['POST'])
def generate_all_missing_formats() -> ResponseReturnValue:
    try:
        service = BulkFormatGeneratorService()
        result = service.generate_all_missing_formats()
        return jsonify(result)
    except Exception as e:
        error_msg = f"Error generating all missing formats: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while generating formats"
        }), 500


@settings.route('/get-generation-log')
def get_generation_log() -> ResponseReturnValue:
    try:
        service = BulkFormatGeneratorService()
        log_data = service.get_generation_log()
        return jsonify(log_data)
    except Exception as e:
        error_msg = f"Error fetching generation log: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        return jsonify({
            "success": False,
            "message": "An error occurred while fetching log"
        }), 500
