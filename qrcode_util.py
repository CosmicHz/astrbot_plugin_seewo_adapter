# -*- coding: utf-8 -*-
"""
二维码图片转 ASCII 文本工具

基于 @石头三颗 的方法：https://zhuanlan.zhihu.com/p/21916363
仅依赖 Pillow。
"""

from PIL import Image

unicode_chr = " ▗▖▄▝▐▞▟▘▚▌▙▀▜▛█"
unicode_mapping = {
    " ": "  ",
    "▗": " ▄",
    "▖": "▄ ",
    "▄": "▄▄",
    "▝": " ▀",
    "▐": " █",
    "▞": "▄▀",
    "▟": "▄█",
    "▘": "▀ ",
    "▚": "▀▄",
    "▌": "█ ",
    "▙": "█▄",
    "▀": "▀▀",
    "▜": "▀█",
    "▛": "█▀",
    "█": "██",
}


def _get_cell_size(img, x, y, x2, y2):
    for j in range(x, x2):
        for i in range(y, y2):
            if img.getpixel((j, i)) == 255:
                return j - x


def _get_cell(img, w, h):
    x1 = 0
    flag = 0
    for y in range(h):
        for x in range(w):
            pix = img.getpixel((x, y))
            if pix == 0 and flag == 0:
                x1 = x
                flag = 1
            if pix == 255 and flag == 1:
                return _get_cell_size(img, x1, x1, x, x)


def qrcode_to_text(file_path: str) -> str:
    """将二维码图片转换为 ASCII 文本字符串"""
    im = Image.open(file_path)
    pil_image = im.crop((15, 15, im.size[0], im.size[1]))
    w, h = pil_image.size
    cell = _get_cell(pil_image, w, h)

    rows = int(h / cell)
    cols = int(w / cell)

    # 构建 bitcode
    bitcode = []
    for y in range(rows):
        row = []
        for x in range(cols):
            pix = pil_image.getpixel((x * cell, y * cell))
            row.append(1 if pix == 0 else 0)
        bitcode.append(row)

    if len(bitcode) % 2 == 1:
        bitcode.append([0] * len(bitcode[0]))

    code = ""
    for i in range(1, len(bitcode), 2):
        for j in range(1, len(bitcode[0]), 2):
            char_index = (
                (bitcode[i - 1][j - 1] << 3)
                + (bitcode[i - 1][j] << 2)
                + (bitcode[i][j - 1] << 1)
                + bitcode[i][j]
            )
            code += unicode_mapping[unicode_chr[char_index]]
        code += "\n"

    return code
