import base64
import os
import tempfile

from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .baidu_face import FACE_MATCH_THRESHOLD, identify_person, match_face, register_faces_for_user
from .identity_utils import resolve_display_name
from .crypto import aes_decrypt_text, aes_encrypt_text
from .models import UserProfile
from .serializers import UserSerializer


def auth_demo(request):
    return render(request, 'auth_demo.html')


def _password_matches(user, password):
    if user.password == password:
        return True
    try:
        return aes_decrypt_text(user.password) == password
    except Exception:
        return False


def _verify_login_face(user, face_image):
    main_face = user.face_images.first()
    if not main_face or not main_face.face_token:
        return False, '用户人脸信息未录入，无法校验', None

    image_base64 = base64.b64encode(face_image.read()).decode()
    result, error = match_face(main_face.face_token, image_base64)
    if error:
        return False, error, None
    if result.get('error_code') != 0:
        return False, f"人脸校验失败: {result.get('error_msg')}", None

    score = result['result']['score']
    if score < FACE_MATCH_THRESHOLD:
        return False, '人脸校验未通过，请重新拍照', score
    return True, '人脸校验通过', score


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def register(request):
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    phone = request.data.get('phone')
    face_images = request.FILES.getlist('face_images')

    if not all([username, password, email, phone]):
        return Response({'msg': '用户名、密码、邮箱和手机号不能为空'}, status=status.HTTP_400_BAD_REQUEST)
    if UserProfile.objects.filter(username=username).exists():
        return Response({'msg': '用户名已存在'}, status=status.HTTP_400_BAD_REQUEST)
    encrypted_email = aes_encrypt_text(email)
    encrypted_phone = aes_encrypt_text(phone)
    if UserProfile.objects.filter(phone=encrypted_phone).exists():
        return Response({'msg': '该手机号已注册，请换一个手机号或直接登录'}, status=status.HTTP_400_BAD_REQUEST)
    if UserProfile.objects.filter(email=encrypted_email).exists():
        return Response({'msg': '该邮箱已注册，请换一个邮箱或直接登录'}, status=status.HTTP_400_BAD_REQUEST)
    if len(face_images) < 3:
        return Response({'msg': '请上传至少三张人脸图片'}, status=status.HTTP_400_BAD_REQUEST)

    user = UserProfile(
        username=username,
        password=aes_encrypt_text(password),
        email=encrypted_email,
        phone=encrypted_phone,
        face_image=face_images[0],
    )
    user.save()

    success_faces = register_faces_for_user(user, face_images, username, email)
    if not success_faces:
        user.delete()
        return Response({'msg': '人脸图片未能成功同步到百度云，请重试'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    request.session['username'] = user.username
    return Response({'msg': '注册成功'}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def login(request):
    username = request.data.get('username') or request.data.get('name')
    password = request.data.get('password')
    face_image = request.FILES.get('face_image') or request.FILES.get('image')

    if not username or not password:
        return Response({'msg': '用户名和密码不能为空'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = UserProfile.objects.get(username=username)
    except UserProfile.DoesNotExist:
        return Response({'msg': '用户不存在'}, status=status.HTTP_400_BAD_REQUEST)

    if not _password_matches(user, password):
        return Response({'msg': '密码错误'}, status=status.HTTP_400_BAD_REQUEST)

    if face_image:
        passed, message, score = _verify_login_face(user, face_image)
        if not passed:
            payload = {'msg': message, 'reason': 'face_mismatch'}
            if score is not None:
                payload['score'] = score
            return Response(payload, status=status.HTTP_401_UNAUTHORIZED)

    request.session['username'] = user.username
    return Response({'msg': '登录成功', 'name': user.username}, status=status.HTTP_200_OK)


@api_view(['POST'])
def logout(request):
    request.session.flush()
    return Response({'msg': '已退出登录'})


@api_view(['GET'])
def current_user_profile(request):
    username = request.session.get('username') or request.GET.get('username')
    if not username:
        return Response({'msg': '未登录'}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        user = UserProfile.objects.get(username=username)
    except UserProfile.DoesNotExist:
        return Response({'msg': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)
    return Response(UserSerializer(user).data)


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def face_recognition(request):
    if 'image' not in request.FILES:
        return Response({'msg': '请上传图片'}, status=status.HTTP_400_BAD_REQUEST)

    image = request.FILES['image']
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp:
        temp_path = temp.name
        for chunk in image.chunks():
            temp.write(chunk)

    try:
        with open(temp_path, 'rb') as file:
            image_base64 = base64.b64encode(file.read()).decode('utf-8')

        identified = identify_person(image_base64)
        if not identified.get('ok'):
            payload = {'msg': identified.get('msg', '识别失败')}
            if identified.get('error_code') is not None:
                payload['error_code'] = identified['error_code']
            if identified.get('score') is not None:
                payload['score'] = identified['score']
            if identified.get('candidates'):
                payload['candidates'] = identified['candidates']
            status_code = status.HTTP_404_NOT_FOUND if identified.get('error_code') == 222207 else status.HTTP_400_BAD_REQUEST
            return Response(payload, status=status_code)

        local_user = None
        try:
            local_user = UserProfile.objects.get(id=identified['user_id'])
        except UserProfile.DoesNotExist:
            local_user = None

        identity = resolve_display_name(
            identified,
            local_username=local_user.username if local_user else None,
        )
        email = None
        if local_user:
            try:
                email = aes_decrypt_text(local_user.email)
            except Exception:
                email = local_user.email
            request.session['username'] = local_user.username

        return Response({
            'msg': '识别成功',
            'identity': identity,
            'user': {
                'id': identified['user_id'],
                'username': identity,
                'email': email,
                'score': identified['score'],
                'user_info': identified.get('user_info', ''),
                'source': 'local_db' if local_user else 'baidu_cloud',
            },
            'candidates': identified.get('candidates', []),
        })
    except Exception as exc:
        return Response({'msg': f'识别过程出错: {str(exc)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def face_verify_one_to_one(request):
    username = request.data.get('username') or request.session.get('username')
    if not username:
        return Response({'msg': '未登录，无法比对'}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        user = UserProfile.objects.get(username=username)
    except UserProfile.DoesNotExist:
        return Response({'msg': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)
    if 'image' not in request.FILES:
        return Response({'msg': '请上传现场图片'}, status=status.HTTP_400_BAD_REQUEST)

    image_base64 = base64.b64encode(request.FILES['image'].read()).decode()
    main_face = user.face_images.first()
    if not main_face or not main_face.face_token:
        return Response({'msg': '用户人脸信息未录入'}, status=status.HTTP_400_BAD_REQUEST)

    result, error = match_face(main_face.face_token, image_base64)
    if error:
        return Response({'msg': error}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    if result.get('error_code') != 0:
        return Response({'msg': f"比对失败: {result.get('error_msg')}"}, status=status.HTTP_400_BAD_REQUEST)

    score = result['result']['score']
    return Response({'msg': '比对成功', 'score': score, 'passed': score >= FACE_MATCH_THRESHOLD})
