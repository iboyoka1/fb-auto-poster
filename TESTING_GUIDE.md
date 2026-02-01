# Testing Guide: Enhanced Facebook Session Features

## Quick Start

### 1. **Access Login Page**
- Go to: `http://localhost:5000/login`
- Click the "Facebook" tab
- You should see the login form with email and password fields

### 2. **Test Facebook Login**

**Valid Login:**
```
Email: test@example.com
Password: testpass123
```

**Expected Behavior:**
- Form validates inputs
- Loading spinner appears
- Green success message shows "Connected as test@example.com"
- Page redirects to dashboard after 1.5 seconds

**Test Validation Errors:**

a) Missing Email:
- Leave email blank → Click "Login to Facebook"
- Error: "Please enter your email or phone number"

b) Missing Password:
- Enter email, leave password blank
- Error: "Please enter your password"

c) Short Password:
- Email: test@example.com, Password: 123
- Error: "Please enter your password"

### 3. **Dashboard Session Display**

**After Successful Login:**
- Session card shows green ✓
- Displays: "Connected as: test@example.com"
- Shows: "Session will persist for 7 days"
- "Logout" button visible

**No Session:**
- Session card shows red ⚠️
- Message: "Facebook Session Not Connected"
- "Login to Facebook" button visible

### 4. **Test Logout**

**From Dashboard:**
1. Click "Logout" button on session card
2. Confirmation dialog appears
3. Click "OK" to confirm
4. Button shows "Logging out..."
5. Toast notification shows success
6. Session card updates immediately
7. Can login again

**From Login Page:**
1. Click "Facebook" tab
2. If already logged in, shows logout button
3. Click "Logout from Facebook"
4. Confirmation dialog appears
5. Session clears and form resets

### 5. **Session Persistence Test**

**Test 7-Day Session:**
1. Login to Facebook (test@example.com)
2. Go to any page
3. Refresh page → Session persists
4. Navigate away and back → Session still active
5. Close browser tab and reopen → Session persists
6. Logout → Session clears completely

### 6. **API Endpoint Tests**

**Using curl or Python:**

```bash
# Check status (before login)
curl http://localhost:5000/api/facebook-status

# Expected: {"connected": false, "email": ""}

# Login
curl -X POST http://localhost:5000/api/facebook-login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'

# Expected: {"success": true, "message": "Logged in as test@example.com", ...}

# Check status (after login)
curl http://localhost:5000/api/facebook-status

# Expected: {"connected": true, "email": "test@example.com", "authenticated": true, ...}

# Logout
curl -X POST http://localhost:5000/api/facebook-logout \
  -H "Content-Type: application/json"

# Expected: {"success": true, "message": "Successfully logged out from Facebook", ...}

# Check status (after logout)
curl http://localhost:5000/api/facebook-status

# Expected: {"connected": false, "email": ""}
```

### 7. **Animation & UX Tests**

**Smooth Animations:**
- ✓ Form slides down on load
- ✓ Error messages shake when displayed
- ✓ Loading spinner spins smoothly
- ✓ Success message slides in
- ✓ Toast notifications slide in from bottom-right
- ✓ Session card fades in/out
- ✓ Buttons have hover effects

**Responsive Design:**
- ✓ Login form works on mobile (< 600px)
- ✓ Dashboard session card responsive
- ✓ Buttons have good touch targets (48px)
- ✓ Form labels readable on all sizes

### 8. **Security Checks**

**Password Security:**
- ✓ Password field masked (dots/asterisks)
- ✓ No password echoed in console
- ✓ No password in error messages
- ✓ No password in logs

**Session Security:**
- ✓ HTTPONLY cookie (JavaScript can't access)
- ✓ SAMESITE=Lax (CSRF protection)
- ✓ Session signed/verified
- ✓ Logout clears ALL session data

**Data Privacy:**
- ✓ Email shown only to logged-in user
- ✓ No user data in API responses
- ✓ Error messages don't leak information
- ✓ Login timestamp tracked but not exposed

## Browser DevTools Checks

### Network Tab:
1. Login request should be POST to `/api/facebook-login`
2. Response includes `"success": true`
3. Cookies set: `session=<token>`
4. Redirect to `/dashboard` after success

### Application/Storage Tab:
1. Check cookies contain `session` value
2. No sensitive data in localStorage
3. Session cookie has HTTPONLY flag
4. Session cookie has SAMESITE=Lax

### Console Tab:
1. No password logged
2. No sensitive errors
3. Can see API responses with success/error
4. Smooth animations don't cause errors

## Troubleshooting

**Issue: Login doesn't work**
- Clear browser cache: Ctrl+Shift+Delete
- Check Flask app is running: http://localhost:5000/login
- Check network tab for error response
- Check Flask logs for error message

**Issue: Session disappears**
- Check if 7 days have passed (unlikely)
- Clear browser cookies and try again
- Restart Flask app
- Check if SESSION_TYPE is set to 'filesystem'

**Issue: Animations are slow**
- Check browser performance: right-click → Inspect → Performance
- Try different browser (Chrome, Firefox, Edge)
- Clear browser cache
- Close other tabs to free up memory

**Issue: Logout doesn't work**
- Check browser console for JavaScript errors
- Verify `/api/facebook-logout` endpoint exists
- Try logout from different page (dashboard vs login)
- Check Flask logs for errors

## Test Checklist

- [ ] Login form displays correctly
- [ ] Email validation works
- [ ] Password validation works
- [ ] Login successful with test@example.com
- [ ] Session persists across page refresh
- [ ] Dashboard shows connected status
- [ ] Logout button visible when logged in
- [ ] Logout clears session
- [ ] All animations are smooth
- [ ] Toast notifications appear
- [ ] Mobile responsive
- [ ] No console errors

## Performance Benchmarks

**Expected Performance:**
- Login request: < 100ms
- Logout request: < 100ms
- Status check: < 50ms
- Page load: < 500ms
- Animation frame rate: 60fps

## Success Criteria

✅ All tests pass
✅ No console errors
✅ Smooth animations at 60fps
✅ Security best practices followed
✅ User experience is improved
✅ Session persists for 7 days
✅ Logout completely clears data

---

**Last Updated:** $(date)
**Test Environment:** Flask Development Server
**Browser:** Chrome/Firefox/Edge (latest)
