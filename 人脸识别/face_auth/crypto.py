import base64
import io

from Crypto.Cipher import AES
from django.core.files.base import ContentFile
from django.db.models import ImageField
from django.db.models.fields.files import ImageFieldFile

AES_KEY = b'\x8f\x1a\x9c\x8e\x1b\x8d\x1e\x8f\x1a\x9c\x8e\x1b\x8d\x1e\x8f\x1a'


def pad(text):
    encoded = text.encode('utf-8')
    padding = 16 - len(encoded) % 16
    return text + chr(padding) * padding


def unpad(text):
    return text[:-ord(text[-1:])]


def aes_encrypt_text(text):
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(text).encode('utf-8'))
    return base64.b64encode(encrypted).decode('utf-8')


def aes_decrypt_text(enc_text):
    cipher = AES.new(AES_KEY, AES.MODE_ECB)
    decrypted = cipher.decrypt(base64.b64decode(enc_text))
    return unpad(decrypted.decode('utf-8'))


def aes_encrypt_image(image_bytes):
    cipher = AES.new(AES_KEY, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(image_bytes)
    return cipher.nonce + tag + ciphertext


def aes_decrypt_image(encrypted_bytes):
    nonce = encrypted_bytes[:16]
    tag = encrypted_bytes[16:32]
    ciphertext = encrypted_bytes[32:]
    cipher = AES.new(AES_KEY, AES.MODE_EAX, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)


class EncryptedImageFieldFile(ImageFieldFile):
    def save(self, name, content, save=True):
        encrypted = aes_encrypt_image(content.read())
        content = ContentFile(encrypted)
        super().save(name, content, save)

    def open(self, mode='rb'):
        file = super().open(mode)
        encrypted = file.read()
        file.close()
        return io.BytesIO(aes_decrypt_image(encrypted))


class EncryptedImageField(ImageField):
    attr_class = EncryptedImageFieldFile
