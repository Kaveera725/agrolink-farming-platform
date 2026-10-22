"""
Image upload, validation, resizing, and cleanup utilities for AgroLink.
Supports JPG, JPEG, PNG, WEBP with 5 MB maximum file size.
"""
import os
import uuid
from typing import Tuple, Optional
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from PIL import Image, ImageOps

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
ALLOWED_PIL_FORMATS = {'JPEG', 'PNG', 'WEBP'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB in bytes


def is_allowed_extension(filename: str) -> bool:
    """Check if the filename has an allowed image extension."""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def get_upload_folder(subfolder: str) -> str:
    """
    Get the absolute path for an upload subfolder inside static/uploads/
    and ensure the directory exists.
    """
    # Base directory is AgroLink/static/uploads/<subfolder>
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', subfolder))
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def resize_image_width(img: Image.Image, target_width: int) -> Image.Image:
    """
    Resizes image maintaining aspect ratio so its width is at most target_width.
    If original width is <= target_width, returns a copy of the image.
    """
    if img.width <= target_width:
        return img.copy()

    ratio = target_width / float(img.width)
    target_height = max(1, int(float(img.height) * ratio))
    return img.resize((target_width, target_height), Image.Resampling.LANCZOS)


def prepare_image_for_saving(img: Image.Image, ext: str) -> Image.Image:
    """
    Ensure image mode is compatible with target extension.
    For JPEG, convert RGBA/LA/P modes to RGB on a white background.
    For PNG and WEBP, keep transparency if present.
    """
    # Auto-orient based on EXIF tags (e.g. smartphone photos taken in portrait)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    normalized_ext = ext.lower().lstrip('.')
    if normalized_ext in ('jpg', 'jpeg'):
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[3])
            return background
        elif img.mode != 'RGB':
            return img.convert('RGB')
    else:
        # PNG or WEBP
        if img.mode not in ('RGB', 'RGBA'):
            return img.convert('RGBA')

    return img


def save_uploaded_image(
    file: Optional[FileStorage],
    folder: str = 'products',
    max_width: int = 1200,
    thumb_width: int = 400
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Validates, renames, resizes, and saves an uploaded image file along with a thumbnail.

    Args:
        file: The uploaded Werkzeug FileStorage object.
        folder: Subdirectory in static/uploads/ (e.g. 'products' or 'profiles').
        max_width: Maximum width for the primary saved image (default: 1200px).
        thumb_width: Width for the generated thumbnail (default: 400px).

    Returns:
        (main_url, thumb_url, error_message)
        On success: error_message is None.
        On failure: main_url and thumb_url are None.
    """
    if not file or not file.filename:
        return None, None, "No file was selected for upload."

    original_filename = secure_filename(file.filename)
    if not is_allowed_extension(original_filename):
        return None, None, "Invalid file extension. Allowed formats are JPG, JPEG, PNG, and WEBP."

    # Validate file size
    try:
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        if size > MAX_FILE_SIZE:
            return None, None, "File size exceeds the 5 MB limit. Please upload a smaller image."
        if size == 0:
            return None, None, "Uploaded file is empty."
    except Exception:
        file.seek(0)

    # Validate actual file contents with Pillow
    try:
        file.seek(0)
        img = Image.open(file.stream)
        
        # Verify format
        if not img.format or img.format.upper() not in ALLOWED_PIL_FORMATS:
            return None, None, "The uploaded file is not a supported image format (JPEG, PNG, WEBP)."

        # Fully load pixel data to detect corrupted or truncated files (and fake images like text files renamed to .jpg)
        img.load()
    except Exception:
        return None, None, "Invalid image file. The file content could not be decoded as an image."

    # Determine file extension (normalize .jpeg to .jpg)
    raw_ext = original_filename.rsplit('.', 1)[1].lower()
    ext = 'jpg' if raw_ext == 'jpeg' else raw_ext

    # Generate secure UUID filename
    file_id = uuid.uuid4().hex
    main_filename = f"{file_id}.{ext}"
    thumb_filename = f"{file_id}_thumb.{ext}"

    upload_dir = get_upload_folder(folder)
    main_path = os.path.join(upload_dir, main_filename)
    thumb_path = os.path.join(upload_dir, thumb_filename)

    try:
        # Resize main image (max width 1200)
        main_img = resize_image_width(img, max_width)
        main_img = prepare_image_for_saving(main_img, ext)

        save_kwargs = {}
        if ext in ('jpg', 'jpeg'):
            save_kwargs['quality'] = 88
            save_kwargs['optimize'] = True
        elif ext == 'webp':
            save_kwargs['quality'] = 88
        elif ext == 'png':
            save_kwargs['optimize'] = True

        main_img.save(main_path, **save_kwargs)

        # Generate thumbnail (400px width)
        thumb_img = resize_image_width(img, thumb_width)
        thumb_img = prepare_image_for_saving(thumb_img, ext)
        thumb_img.save(thumb_path, **save_kwargs)

    except Exception as e:
        # Cleanup any partially created files on failure
        if os.path.exists(main_path):
            try: os.remove(main_path)
            except OSError: pass
        if os.path.exists(thumb_path):
            try: os.remove(thumb_path)
            except OSError: pass
        return None, None, f"Failed to process and save image: {str(e)}"

    main_url = f"/static/uploads/{folder}/{main_filename}"
    thumb_url = f"/static/uploads/{folder}/{thumb_filename}"
    return main_url, thumb_url, None


def delete_uploaded_image(image_url: Optional[str]) -> bool:
    """
    Safely deletes a local uploaded image and its thumbnail from disk.
    Only deletes files located inside static/uploads/.
    Ignores external/remote stock URLs.
    """
    if not image_url or not isinstance(image_url, str):
        return False

    if not image_url.startswith('/static/uploads/'):
        return False

    # Convert web path to absolute file path
    rel_path = image_url.lstrip('/').replace('/', os.sep)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    full_path = os.path.abspath(os.path.join(project_root, rel_path))

    # Security check: ensure path is strictly inside static/uploads/
    allowed_base = os.path.abspath(os.path.join(project_root, 'static', 'uploads'))
    if not full_path.startswith(allowed_base):
        return False

    deleted = False
    # 1. Delete main file
    if os.path.isfile(full_path):
        try:
            os.remove(full_path)
            deleted = True
        except OSError:
            pass

    # 2. Delete thumbnail if exists
    base, ext = os.path.splitext(full_path)
    if not base.endswith('_thumb'):
        thumb_path = f"{base}_thumb{ext}"
        if os.path.isfile(thumb_path):
            try:
                os.remove(thumb_path)
            except OSError:
                pass

    return deleted
