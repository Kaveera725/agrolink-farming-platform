import os, sys, re
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app

app_instance = app.create_app()

def get_csrf(data):
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', data.decode('utf-8'))
    return m.group(1) if m else ''

with app_instance.test_client() as client:
    # 1. GET /auth/login
    r = client.get('/auth/login')
    assert r.status_code == 200, f'Login GET failed: {r.status_code}'
    assert b'Sign in to your account' in r.data, 'Login heading missing'
    assert b'No Middlemen' in r.data, 'Brand panel benefits missing in login'
    csrf_login = get_csrf(r.data)
    print('PASS: Login GET 200 OK with split-screen brand panel')

    # 2. POST /auth/login bad credentials
    r = client.post('/auth/login', data={'csrf_token': csrf_login, 'email': 'nobody@test.com', 'password': 'wrongpassword'}, follow_redirects=True)
    assert r.status_code == 200, f'Login POST failed: {r.status_code}'
    assert b'Invalid email or password' in r.data, 'Login flash error missing'
    print('PASS: Login POST bad credentials handled & re-rendered 200 OK')

    # 3. GET /auth/register
    r = client.get('/auth/register')
    assert r.status_code == 200, f'Register GET failed: {r.status_code}'
    assert b'Create your account' in r.data, 'Register heading missing'
    assert b'role-farmer' in r.data, 'Role farmer radio missing'
    assert b'role-buyer' in r.data, 'Role buyer radio missing'
    assert b'Password Strength:' in r.data, 'Strength meter missing'
    assert b'reg-location-picker' in r.data, 'Map slot missing'
    csrf_reg = get_csrf(r.data)
    print('PASS: Register GET 200 OK with role cards and grouped sections')

    # 4. POST /auth/register with server-side validation error (passwords do not match)
    data = {
        'csrf_token': csrf_reg,
        'role': 'farmer',
        'name': 'Test Farmer User',
        'email': 'validnewemail@agrolink.lk',
        'password': 'password123',
        'confirm_password': 'mismatchpassword',
        'whatsapp_number': '0771234567',
        'phone': '0112345678',
        'location': 'Kandy'
    }
    r = client.post('/auth/register', data=data, follow_redirects=True)
    assert r.status_code == 200, f'Register POST mismatch failed: {r.status_code}'
    assert b'Passwords do not match' in r.data, 'Passwords mismatch flash missing'
    assert b'Test Farmer User' in r.data, 'Preserved name missing in re-render'
    assert b'validnewemail@agrolink.lk' in r.data, 'Preserved email missing in re-render'
    assert b'771234567' in r.data, 'Preserved whatsapp missing in re-render'
    assert b'0112345678' in r.data, 'Preserved phone missing in re-render'
    assert b'Kandy' in r.data, 'Preserved district missing'
    print('PASS: Register POST mismatch preserved all form fields & re-rendered 200 OK')

    # 5. POST /auth/register with invalid WhatsApp number
    csrf_reg2 = get_csrf(r.data)
    data['csrf_token'] = csrf_reg2
    data['confirm_password'] = 'password123'
    data['whatsapp_number'] = '12345'
    r = client.post('/auth/register', data=data, follow_redirects=True)
    assert r.status_code == 200, f'Register POST bad phone failed: {r.status_code}'
    assert b'Please enter a valid' in r.data or b'Sri Lankan WhatsApp number' in r.data, 'Bad phone flash missing'
    print('PASS: Register POST invalid WhatsApp handled cleanly & re-rendered 200 OK')

print('\nALL AUTH VERIFICATION TESTS PASSED!')
