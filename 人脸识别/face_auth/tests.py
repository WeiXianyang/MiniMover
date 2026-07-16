from django.test import TestCase


class AuthDemoTemplateTests(TestCase):
    def test_camera_control_is_wired_for_the_jetson_stream(self):
        response = self.client.get('/api/')

        self.assertContains(response, 'id="carCam"')
        self.assertContains(response, "5000/video_feed")
        self.assertContains(response, "camMode === 'car'")
        self.assertContains(response, 'id="cameraOverlay"')
        self.assertContains(response, "No CameraNAVmode OK without cam")
