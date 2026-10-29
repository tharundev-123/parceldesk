/**
 * ParcelDesk — Modern Logistics SaaS Application Controller
 * Design Theme: Carbon + Signal Orange
 * Preserves 100% backend API contracts, 3NF transactions, and security models.
 */

let currentUser = null;
let allStudentsList = [];
let allGuardParcels = [];
let activeStatusFilter = 'all';
let activeCourierFilter = '';
let timerIntervals = {};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    initClock();
    checkCurrentUser();
});

// -------------------------------------------------------------
// Live Digital Station Clock
// -------------------------------------------------------------
function initClock() {
    const clockElem = document.getElementById('station-clock');
    const updateTime = () => {
        const now = new Date();
        const hrs = String(now.getHours()).padStart(2, '0');
        const mins = String(now.getMinutes()).padStart(2, '0');
        const secs = String(now.getSeconds()).padStart(2, '0');
        if (clockElem) clockElem.textContent = `${hrs}:${mins}:${secs}`;
    };
    updateTime();
    setInterval(updateTime, 1000);
}

// -------------------------------------------------------------
// Authentication & Role Routing
// -------------------------------------------------------------
async function checkCurrentUser() {
    try {
        const res = await fetch('/api/me');
        const data = await res.json();
        if (data.authenticated && data.user) {
            setUserState(data.user);
        } else {
            // Default demo auto-login as gate guard for immediate preview
            await demoLogin('guard1', 'guard123', false);
        }
    } catch (err) {
        console.error('Session check failed:', err);
        showToast('Failed to connect to backend server.', 'error');
    }
}

function setUserState(user) {
    currentUser = user;

    // Update User Profile Footer
    const nameElem = document.getElementById('user-display-name');
    const roleElem = document.getElementById('user-role-pill');
    const avatarElem = document.getElementById('sidebar-avatar');

    if (nameElem) nameElem.textContent = user.full_name;
    if (roleElem) {
        roleElem.textContent = user.role.toUpperCase();
        roleElem.className = `user-meta-role text-orange`;
    }
    if (avatarElem) {
        avatarElem.textContent = (user.full_name || 'U').charAt(0).toUpperCase();
    }

    // Sync Persona Select Dropdown
    const personaSelect = document.getElementById('persona-select');
    if (personaSelect) {
        personaSelect.value = user.username;
    }

    // Update Topbar Station Context
    const contextTitle = document.getElementById('topbar-context-title');
    const topbarActions = document.getElementById('topbar-guard-actions');

    // Hide all role workspaces
    document.getElementById('guard-view').classList.add('hidden');
    document.getElementById('student-view').classList.add('hidden');
    document.getElementById('warden-view').classList.add('hidden');

    // Hide all sidebar nav sections
    document.getElementById('nav-guard-section').classList.add('hidden');
    document.getElementById('nav-student-section').classList.add('hidden');
    document.getElementById('nav-warden-section').classList.add('hidden');

    if (user.role === 'guard') {
        document.getElementById('guard-view').classList.remove('hidden');
        document.getElementById('nav-guard-section').classList.remove('hidden');
        if (contextTitle) contextTitle.textContent = 'GATE OPERATIONS // LIVE CONSOLE';
        if (topbarActions) topbarActions.classList.remove('hidden');
        loadGuardParcels();
        loadStudentsDropdown();
    } else if (user.role === 'student') {
        document.getElementById('student-view').classList.remove('hidden');
        document.getElementById('nav-student-section').classList.remove('hidden');
        if (contextTitle) contextTitle.textContent = 'RESIDENT PORTAL // MY DELIVERIES';
        if (topbarActions) topbarActions.classList.add('hidden');
        
        document.getElementById('student-portal-name').textContent = user.full_name;
        if (user.student_profile) {
            document.getElementById('student-portal-details').textContent = 
                `Roll No: ${user.student_profile.student_roll_no} | Room: ${user.student_profile.room_no} | ${user.student_profile.hostel_name}`;
        }
        loadStudentDeliveries();
        loadStudentNotifications();
    } else if (user.role === 'warden' || user.role === 'admin') {
        document.getElementById('warden-view').classList.remove('hidden');
        document.getElementById('nav-warden-section').classList.remove('hidden');
        if (contextTitle) contextTitle.textContent = 'CAMPUS LOGISTICS // AUDIT & ANALYTICS';
        if (topbarActions) topbarActions.classList.add('hidden');
        loadWardenDashboard();
        loadAuditLogs();
    }
}

async function demoLogin(username, password, showNotify = true) {
    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (res.ok) {
            if (showNotify) {
                showToast(`Switched persona to ${data.user.full_name} (${data.user.role.toUpperCase()})`, 'success');
            }
            setUserState(data.user);
        } else {
            showToast(data.error || 'Authentication failed', 'error');
        }
    } catch (err) {
        showToast('Network error during authentication.', 'error');
    }
}

function handlePersonaSelectChange(selectElem) {
    const val = selectElem.value;
    const creds = {
        'guard1': 'guard123',
        'student1': 'student123',
        'student2': 'student123',
        'warden1': 'warden123',
        'admin': 'admin123'
    };
    if (creds[val]) {
        demoLogin(val, creds[val]);
    }
}

async function handleLogout() {
    try {
        await fetch('/api/logout', { method: 'POST' });
        currentUser = null;
        showToast('Signed out of terminal.', 'info');
        demoLogin('guard1', 'guard123', false);
    } catch (err) {
        console.error('Logout error:', err);
    }
}

// -------------------------------------------------------------
// Sidebar Collapse & Mobile Navigation
// -------------------------------------------------------------
function toggleSidebarCollapse() {
    const sidebar = document.getElementById('saas-sidebar');
    sidebar.classList.toggle('collapsed');
}

function toggleMobileMenu() {
    const sidebar = document.getElementById('saas-sidebar');
    const backdrop = document.getElementById('mobile-backdrop');
    sidebar.classList.toggle('mobile-open');
    backdrop.classList.toggle('active');
}

function activateNav(linkElem, targetViewId) {
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    linkElem.classList.add('active');
    
    if (window.innerWidth <= 900) {
        toggleMobileMenu();
    }
}

// -------------------------------------------------------------
// Slide-Over Notification Centre Drawer
// -------------------------------------------------------------
function toggleNotificationsDrawer() {
    const drawer = document.getElementById('drawer-notifications');
    drawer.classList.toggle('hidden');
    if (!drawer.classList.contains('hidden') && currentUser && currentUser.role === 'student') {
        loadStudentNotifications();
    }
}

// -------------------------------------------------------------
// Gate Staff Operations (Parcels Management)
// -------------------------------------------------------------
async function loadGuardParcels() {
    try {
        const res = await fetch('/api/parcels');
        const data = await res.json();
        if (res.ok) {
            allGuardParcels = data.parcels || [];
            applyCombinedFilters();
            updateGuardKPIs(allGuardParcels);
        }
    } catch (err) {
        console.error('Failed to load parcels:', err);
    }
}

function updateGuardKPIs(parcels) {
    const pending = parcels.filter(p => p.status === 'received' || p.status === 'notified').length;
    const collected = parcels.filter(p => p.status === 'collected').length;
    
    const todayStr = new Date().toISOString().slice(0, 10);
    const todayCount = parcels.filter(p => p.received_at && p.received_at.startsWith(todayStr)).length;

    document.getElementById('guard-pending-count').textContent = pending;
    document.getElementById('guard-today-count').textContent = todayCount;
    document.getElementById('guard-collected-count').textContent = collected;

    const sbBadge = document.getElementById('sidebar-pending-badge');
    if (sbBadge) sbBadge.textContent = pending;
}

// Multi-Criteria Table Filtering
function applyParcelFilter(status, pillElem) {
    activeStatusFilter = status;
    document.querySelectorAll('.filter-pill').forEach(btn => btn.classList.remove('active'));
    if (pillElem) pillElem.classList.add('active');
    applyCombinedFilters();
}

function applyCourierFilter(courierName) {
    activeCourierFilter = courierName;
    applyCombinedFilters();
}

function filterGuardTable() {
    applyCombinedFilters();
}

function applyCombinedFilters() {
    const searchVal = (document.getElementById('guard-search-input')?.value || '').toLowerCase().trim();

    let filtered = allGuardParcels.filter(p => {
        // 1. Status Filter
        if (activeStatusFilter === 'pending' && !(p.status === 'received' || p.status === 'notified')) return false;
        if (activeStatusFilter === 'notified' && p.status !== 'notified') return false;
        if (activeStatusFilter === 'collected' && p.status !== 'collected') return false;

        // 2. Courier Filter
        if (activeCourierFilter && p.courier_name !== activeCourierFilter) return false;

        // 3. Search Query
        if (searchVal) {
            const match = (p.tracking_number && p.tracking_number.toLowerCase().includes(searchVal)) ||
                          (p.student_name && p.student_name.toLowerCase().includes(searchVal)) ||
                          (p.student_roll_no && p.student_roll_no.toLowerCase().includes(searchVal)) ||
                          (p.room_no && p.room_no.toLowerCase().includes(searchVal)) ||
                          (p.courier_name && p.courier_name.toLowerCase().includes(searchVal));
            if (!match) return false;
        }

        return true;
    });

    renderGuardTable(filtered);
}

function renderGuardTable(parcels) {
    const tbody = document.getElementById('guard-parcels-tbody');
    tbody.innerHTML = '';

    if (!parcels || parcels.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center empty-state">No matching packages found.</td></tr>`;
        return;
    }

    parcels.forEach(p => {
        const tr = document.createElement('tr');

        // Waiting Duration
        const recDate = new Date(p.received_at);
        const diffHrs = Math.max(0, Math.round((new Date() - recDate) / (1000 * 60 * 60) * 10) / 10);

        // Status Badge Style
        const badgeClass = p.status === 'collected' ? 'badge-collected' : (p.status === 'notified' ? 'badge-notified' : 'badge-received');
        
        // Photo Thumbnail
        const photoHtml = p.photo_url 
            ? `<img src="${p.photo_url}" class="table-photo-thumb" alt="Parcel Photo" onclick="viewPhoto('${p.photo_url}', '${p.tracking_number}')" title="Inspect Photo">`
            : `<span style="font-family:var(--font-mono);font-size:0.7rem;color:var(--text-muted);">NO PHOTO</span>`;

        // Action Buttons
        let actionsHtml = '';
        if (p.status !== 'collected') {
            actionsHtml = `
                <div style="display:flex;gap:0.4rem;justify-content:flex-end;">
                    <button class="btn btn-primary btn-sm" onclick="openHandoverModal(${p.id})">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                        <span>Hand Over</span>
                    </button>
                    <button class="btn btn-secondary btn-sm" onclick="triggerNotify(${p.id})" title="Resend Notification">🔔</button>
                </div>
            `;
        } else {
            actionsHtml = `
                <div style="display:flex;justify-content:flex-end;">
                    <span class="badge badge-collected">✓ Handed Over</span>
                </div>
            `;
        }

        tr.innerHTML = `
            <td>
                <div style="font-weight:700;color:var(--text-primary);">${escapeHtml(p.courier_name)}</div>
                <div style="font-family:var(--font-mono);font-size:0.75rem;color:var(--orange-primary);display:flex;align-items:center;gap:0.4rem;margin-top:0.15rem;">
                    <span>${escapeHtml(p.tracking_number)}</span>
                    <button class="btn-icon" style="padding:0.1rem 0.3rem;font-size:0.65rem;" onclick="copyToClipboard('${p.tracking_number}', 'Tracking #')">📋</button>
                </div>
            </td>
            <td>
                <div style="font-weight:700;">${escapeHtml(p.student_name)}</div>
                <div style="font-family:var(--font-mono);font-size:0.74rem;color:var(--text-muted);">${escapeHtml(p.student_roll_no)}</div>
            </td>
            <td>
                <div>${escapeHtml(p.hostel_name)} (${escapeHtml(p.hostel_code)})</div>
                <div style="font-family:var(--font-mono);font-size:0.74rem;color:var(--text-muted);">${escapeHtml(p.room_no)}</div>
            </td>
            <td style="font-family:var(--font-mono);font-size:0.78rem;">${formatDate(p.received_at)}</td>
            <td style="font-family:var(--font-mono);font-size:0.78rem;">${p.status === 'collected' ? '-' : `<span class="kpi-tag tag-orange">${diffHrs} hrs</span>`}</td>
            <td>${photoHtml}</td>
            <td><span class="badge ${badgeClass}">${p.status}</span></td>
            <td>${actionsHtml}</td>
        `;
        tbody.appendChild(tr);
    });
}

async function loadStudentsDropdown() {
    try {
        const res = await fetch('/api/students');
        const data = await res.json();
        if (res.ok) {
            allStudentsList = data.students || [];
            const select = document.getElementById('input-student-select');
            select.innerHTML = '<option value="">-- Select Student Recipient --</option>';
            allStudentsList.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.student_id;
                opt.textContent = `${s.student_name} (${s.student_roll_no} - ${s.hostel_code} ${s.room_no})`;
                select.appendChild(opt);
            });
        }
    } catch (err) {
        console.error('Failed to load students list:', err);
    }
}

function handleStudentSelectChange(selectElem) {
    const studentId = parseInt(selectElem.value);
    const student = allStudentsList.find(s => s.student_id === studentId);
    if (student) {
        document.getElementById('input-hostel-display').value = `${student.hostel_name} — ${student.room_no}`;
        document.getElementById('input-hostel-id').value = student.hostel_id;
    } else {
        document.getElementById('input-hostel-display').value = '';
        document.getElementById('input-hostel-id').value = '';
    }
}

function generateRandomTracking() {
    const prefix = ['AMZ', 'FK', 'BLR', 'DLV', 'EXP'][Math.floor(Math.random() * 5)];
    const num = Math.floor(100000 + Math.random() * 900000);
    document.getElementById('input-tracking').value = `${prefix}-${num}`;
}

function previewPhoto(input) {
    const previewBox = document.getElementById('photo-preview-box');
    const previewImg = document.getElementById('photo-preview-img');
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = (e) => {
            previewImg.src = e.target.result;
            previewBox.classList.remove('hidden');
        };
        reader.readAsDataURL(input.files[0]);
    } else {
        previewBox.classList.add('hidden');
    }
}

function openLogParcelModal() {
    document.getElementById('form-log-parcel').reset();
    document.getElementById('photo-preview-box').classList.add('hidden');
    generateRandomTracking();
    document.getElementById('modal-log-parcel').classList.remove('hidden');
}

async function handleLogParcelSubmit(event) {
    event.preventDefault();
    const btn = document.getElementById('btn-submit-parcel');
    btn.disabled = true;
    btn.querySelector('span').textContent = 'Uploading & Logging...';

    const studentId = document.getElementById('input-student-select').value;
    const hostelId = document.getElementById('input-hostel-id').value;
    const courier = document.getElementById('input-courier').value;
    const tracking = document.getElementById('input-tracking').value;
    const remarks = document.getElementById('input-remarks').value;
    const photoFile = document.getElementById('input-photo').files[0];

    const formData = new FormData();
    formData.append('student_id', studentId);
    formData.append('hostel_id', hostelId);
    formData.append('courier_name', courier);
    formData.append('tracking_number', tracking);
    formData.append('remarks', remarks);
    if (photoFile) {
        formData.append('photo', photoFile);
    }

    try {
        const res = await fetch('/api/parcels', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (res.ok) {
            closeModal('modal-log-parcel');
            showToast(`Parcel registered! Single-use OTP generated and student notified.`, 'success');
            loadGuardParcels();
        } else {
            showToast(data.error || 'Failed to log parcel', 'error');
        }
    } catch (err) {
        showToast('Error uploading parcel.', 'error');
    } finally {
        btn.disabled = false;
        btn.querySelector('span').textContent = 'Save & Dispatch Notification';
    }
}

async function triggerNotify(parcelId) {
    try {
        const res = await fetch(`/api/parcels/${parcelId}/notify`, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            showToast('Notification alert dispatched to student!', 'success');
            loadGuardParcels();
        } else {
            showToast(data.error || 'Notification failed', 'error');
        }
    } catch (err) {
        showToast('Network error dispatching notification', 'error');
    }
}

// -------------------------------------------------------------
// Handover & OTP Verification (ACID Transaction)
// -------------------------------------------------------------
function openHandoverModal(preselectedParcelId = null) {
    const select = document.getElementById('handover-parcel-select');
    select.innerHTML = '<option value="">-- Choose parcel to verify --</option>';

    const pending = allGuardParcels.filter(p => p.status === 'received' || p.status === 'notified');
    pending.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = `[${p.courier_name}] ${p.tracking_number} — ${p.student_name} (${p.hostel_code} ${p.room_no})`;
        select.appendChild(opt);
    });

    if (preselectedParcelId) {
        select.value = preselectedParcelId;
        handleHandoverParcelChange(select);
    } else {
        document.getElementById('handover-parcel-summary').classList.add('hidden');
    }

    document.getElementById('handover-otp-input').value = '';
    document.getElementById('handover-notes').value = '';
    document.getElementById('modal-handover').classList.remove('hidden');
    document.getElementById('handover-otp-input').focus();
}

function handleHandoverParcelChange(selectElem) {
    const parcelId = parseInt(selectElem.value);
    const summaryBox = document.getElementById('handover-parcel-summary');
    const parcel = allGuardParcels.find(p => p.id === parcelId);

    if (parcel) {
        summaryBox.innerHTML = `
            <div><strong>Recipient:</strong> ${escapeHtml(parcel.student_name)} (Roll: ${escapeHtml(parcel.student_roll_no)})</div>
            <div><strong>Hostel & Room:</strong> ${escapeHtml(parcel.hostel_name)} — Room ${escapeHtml(parcel.room_no)}</div>
            <div><strong>Courier:</strong> ${escapeHtml(parcel.courier_name)} (<span style="color:var(--orange-primary);font-family:var(--font-mono);">${escapeHtml(parcel.tracking_number)}</span>)</div>
        `;
        summaryBox.classList.remove('hidden');
    } else {
        summaryBox.classList.add('hidden');
    }
}

async function handleHandoverSubmit(event) {
    event.preventDefault();
    const parcelId = document.getElementById('handover-parcel-select').value;
    const otp = document.getElementById('handover-otp-input').value.trim();
    const notes = document.getElementById('handover-notes').value.trim();
    const btn = document.getElementById('btn-submit-handover');

    if (!parcelId || !otp) {
        showToast('Please select parcel and input the 6-digit passcode.', 'error');
        return;
    }

    btn.disabled = true;
    btn.querySelector('span').textContent = 'Verifying Hash in Database...';

    try {
        const res = await fetch(`/api/parcels/${parcelId}/handover`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ otp, notes })
        });
        const data = await res.json();

        if (res.ok) {
            closeModal('modal-handover');
            showToast('✓ OTP Verified! Transaction committed and package released.', 'success');
            loadGuardParcels();
        } else {
            showToast(data.error || 'Verification failed', 'error');
        }
    } catch (err) {
        showToast('Error executing handover transaction.', 'error');
    } finally {
        btn.disabled = false;
        btn.querySelector('span').textContent = 'Verify & Release Parcel';
    }
}

// -------------------------------------------------------------
// Student Portal Deliveries & Passcode Tracking
// -------------------------------------------------------------
async function loadStudentDeliveries() {
    try {
        const res = await fetch('/api/parcels');
        const data = await res.json();
        if (res.ok) {
            renderStudentParcels(data.parcels || []);
        }
    } catch (err) {
        console.error('Failed to load student parcels:', err);
    }
}

function renderStudentParcels(parcels) {
    const container = document.getElementById('student-parcels-list');
    container.innerHTML = '';

    const pendingParcels = parcels.filter(p => p.status !== 'collected');
    const studentActiveCountElem = document.getElementById('student-active-count');
    const sidebarStudentBadge = document.getElementById('sidebar-student-badge');
    
    if (studentActiveCountElem) studentActiveCountElem.textContent = pendingParcels.length;
    if (sidebarStudentBadge) sidebarStudentBadge.textContent = pendingParcels.length;

    if (!parcels || parcels.length === 0) {
        container.innerHTML = `<div class="empty-state">No shipments registered for your room yet.</div>`;
        return;
    }

    parcels.forEach(p => {
        const card = document.createElement('div');
        card.className = 'student-parcel-card';

        const isCollected = p.status === 'collected';
        const isNotified = p.status === 'notified';

        const s1Active = 'completed';
        const s2Active = isNotified || isCollected ? 'completed' : 'active';
        const s3Active = isCollected ? 'completed' : '';

        let otpSection = '';
        if (!isCollected) {
            otpSection = `
                <div class="otp-showcase">
                    <div>
                        <div class="otp-tag">COLLECTION PASSCODE</div>
                        <div class="otp-digits" id="otp-display-${p.id}">••••••</div>
                        <div class="otp-expiry" id="otp-timer-${p.id}">Single-use SHA-256 hash</div>
                    </div>
                    <div>
                        <button class="btn btn-primary" onclick="requestStudentOtp(${p.id})">
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                            <span>Reveal / Refresh OTP</span>
                        </button>
                    </div>
                </div>
            `;
        } else {
            otpSection = `
                <div style="background:var(--success-subtle);border:1px solid var(--success-border);padding:0.85rem 1.1rem;border-radius:var(--radius-sm);color:var(--success);font-family:var(--font-mono);font-size:0.84rem;display:flex;align-items:center;gap:0.5rem;">
                    <span>✓ Collected and verified on ${formatDate(p.collected_at || p.handover_time)}</span>
                </div>
            `;
        }

        const photoSection = p.photo_url ? `
            <div style="margin-top:0.4rem;">
                <span style="font-family:var(--font-mono);font-size:0.72rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">PACKAGE CONDITION (AZURE BLOB):</span>
                <img src="${p.photo_url}" class="table-photo-thumb" style="width:64px;height:64px;" onclick="viewPhoto('${p.photo_url}', '${p.tracking_number}')" title="Click to enlarge">
            </div>
        ` : '';

        card.innerHTML = `
            <div class="parcel-top">
                <div>
                    <div class="parcel-title">${escapeHtml(p.courier_name)}</div>
                    <div class="parcel-meta">
                        Tracking: <strong style="color:var(--orange-primary);font-family:var(--font-mono);">${escapeHtml(p.tracking_number)}</strong> | Received: ${formatDate(p.received_at)}
                    </div>
                    ${p.remarks ? `<div style="font-size:0.82rem;color:var(--text-secondary);margin-top:0.25rem;">Note: ${escapeHtml(p.remarks)}</div>` : ''}
                </div>
                <span class="badge ${isCollected ? 'badge-collected' : 'badge-notified'}">${p.status}</span>
            </div>

            <!-- Lifecycle Stepper -->
            <div class="timeline-stepper">
                <div class="timeline-line"></div>
                <div class="step-item ${s1Active}">
                    <div class="step-circle">1</div>
                    <div class="step-label">Received</div>
                </div>
                <div class="step-item ${s2Active}">
                    <div class="step-circle">2</div>
                    <div class="step-label">Notified</div>
                </div>
                <div class="step-item ${s3Active}">
                    <div class="step-circle">3</div>
                    <div class="step-label">Collected</div>
                </div>
            </div>

            ${otpSection}
            ${photoSection}
        `;

        container.appendChild(card);
    });
}

async function requestStudentOtp(parcelId) {
    try {
        const res = await fetch(`/api/parcels/${parcelId}/regenerate-otp`, { method: 'POST' });
        const data = await res.json();
        if (res.ok && data.otp_data) {
            const code = data.otp_data.plain_otp;
            const elem = document.getElementById(`otp-display-${parcelId}`);
            if (elem) {
                elem.textContent = `${code.slice(0, 3)} ${code.slice(3)}`;
            }
            startOtpCountdown(parcelId, data.otp_data.otp_expiry);
            showToast('Passcode generated! Show code to gate staff.', 'success');
        } else {
            showToast(data.error || 'Failed to generate OTP', 'error');
        }
    } catch (err) {
        showToast('Network error requesting OTP.', 'error');
    }
}

function startOtpCountdown(parcelId, expiryStr) {
    if (timerIntervals[parcelId]) {
        clearInterval(timerIntervals[parcelId]);
    }
    const expiryTime = new Date(expiryStr).getTime();

    const updateTimer = () => {
        const now = new Date().getTime();
        const distance = expiryTime - now;
        const timerElem = document.getElementById(`otp-timer-${parcelId}`);

        if (!timerElem) {
            clearInterval(timerIntervals[parcelId]);
            return;
        }

        if (distance <= 0) {
            timerElem.textContent = 'Expired. Please refresh.';
            timerElem.style.color = 'var(--error)';
            clearInterval(timerIntervals[parcelId]);
        } else {
            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((distance % (1000 * 60)) / 1000);
            timerElem.textContent = `Expires in ${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
            timerElem.style.color = 'var(--warning)';
        }
    };

    updateTimer();
    timerIntervals[parcelId] = setInterval(updateTimer, 1000);
}

async function loadStudentNotifications() {
    try {
        const res = await fetch('/api/notifications');
        const data = await res.json();
        if (res.ok) {
            const notifs = data.notifications || [];
            renderNotificationFeeds(notifs);
        }
    } catch (err) {
        console.error('Failed to load notifications:', err);
    }
}

function renderNotificationFeeds(notifs) {
    const mainFeed = document.getElementById('student-notifications-feed');
    const drawerFeed = document.getElementById('drawer-notif-content');

    const htmlContent = notifs.length === 0 
        ? `<div class="empty-state">No notifications.</div>`
        : notifs.map(n => `
            <div class="notif-card" onclick="viewJsonPayload(${escapeJsonArg(n.payload)})">
                <div class="notif-card-header">
                    <span>📦 ${escapeHtml(n.courier_name)} Arrived</span>
                    <span class="notif-time">${formatDate(n.sent_at)}</span>
                </div>
                <p style="color:var(--text-secondary);font-size:0.82rem;">
                    ${n.payload && n.payload.message ? escapeHtml(n.payload.message) : `Parcel ${n.tracking_number} received.`}
                </p>
                <div style="font-size:0.72rem;color:var(--orange-primary);margin-top:0.4rem;font-weight:700;font-family:var(--font-mono);">
                    🔍 View DP-900 JSON Document
                </div>
            </div>
        `).join('');

    if (mainFeed) mainFeed.innerHTML = htmlContent;
    if (drawerFeed) drawerFeed.innerHTML = htmlContent;
}

// -------------------------------------------------------------
// Warden & Admin Analytics (DP-900 & Cloud Security)
// -------------------------------------------------------------
async function loadWardenDashboard() {
    try {
        const res = await fetch('/api/analytics/summary');
        const data = await res.json();
        if (res.ok) {
            const summary = data.summary || {};
            document.getElementById('warden-total-parcels').textContent = summary.total_parcels || 0;
            document.getElementById('warden-pending-parcels').textContent = summary.pending_parcels || 0;
            document.getElementById('warden-collected-parcels').textContent = summary.collected_parcels || 0;
            document.getElementById('warden-avg-time').textContent = `${summary.avg_pickup_hours || 0} hrs`;

            renderHostelDistribution(summary.pending_by_hostel || []);
        }
    } catch (err) {
        console.error('Failed to load analytics summary:', err);
    }
}

function renderHostelDistribution(hostels) {
    const container = document.getElementById('hostel-distribution-bars');
    container.innerHTML = '';

    if (!hostels || hostels.length === 0) {
        container.innerHTML = '<div class="empty-state">No hostel distribution data available.</div>';
        return;
    }

    const maxCount = Math.max(...hostels.map(h => h.pending_count || 0), 1);

    hostels.forEach(h => {
        const count = h.pending_count || 0;
        const percentage = Math.round((count / maxCount) * 100);

        const item = document.createElement('div');
        item.className = 'dist-bar-item';
        item.innerHTML = `
            <div class="dist-bar-header">
                <span>${escapeHtml(h.hostel_name)} (${escapeHtml(h.hostel_code)})</span>
                <span style="color:var(--orange-primary);font-family:var(--font-mono);font-weight:700;">${count} parcels</span>
            </div>
            <div class="dist-bar-track">
                <div class="dist-bar-fill" style="width: ${Math.max(percentage, 6)}%"></div>
            </div>
        `;
        container.appendChild(item);
    });
}

async function loadAuditLogs() {
    try {
        const res = await fetch('/api/audit-logs');
        const data = await res.json();
        if (res.ok) {
            const tbody = document.getElementById('audit-logs-tbody');
            tbody.innerHTML = '';
            const logs = data.audit_logs || [];

            if (logs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center empty-state">No audit records found.</td></tr>';
                return;
            }

            logs.forEach(l => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-family:var(--font-mono);font-size:0.75rem;">${formatDate(l.created_at)}</td>
                    <td><strong style="color:var(--orange-primary);font-family:var(--font-mono);">${escapeHtml(l.action)}</strong></td>
                    <td>${escapeHtml(l.full_name || l.username || 'System')}</td>
                    <td><span class="kpi-tag tag-blue">${escapeHtml(l.role || 'system')}</span></td>
                    <td style="font-family:var(--font-mono);font-size:0.75rem;color:var(--text-muted);">${escapeHtml(l.ip_address || '127.0.0.1')}</td>
                    <td style="font-size:0.8rem;color:var(--text-secondary);max-width:320px;word-break:break-all;">${escapeHtml(l.details || '-')}</td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (err) {
        console.error('Failed to load audit logs:', err);
    }
}

// -------------------------------------------------------------
// Utilities, Modals & Photo Viewer
// -------------------------------------------------------------
function copyToClipboard(text, label = 'Code') {
    navigator.clipboard.writeText(text).then(() => {
        showToast(`${label} copied to clipboard!`, 'info');
    });
}

function viewPhoto(url, title = 'Parcel Photo') {
    document.getElementById('image-modal-title').textContent = `Package Condition (${title})`;
    document.getElementById('image-modal-img').src = url;
    document.getElementById('modal-image-viewer').classList.remove('hidden');
}

function viewJsonPayload(payload) {
    document.getElementById('json-viewer-content').textContent = JSON.stringify(payload, null, 2);
    document.getElementById('modal-json-viewer').classList.remove('hidden');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.add('hidden');
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    try {
        const d = new Date(dateStr.replace(' ', 'T'));
        return d.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return dateStr;
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function escapeJsonArg(obj) {
    if (!obj) return '{}';
    return JSON.stringify(obj).replace(/"/g, '&quot;');
}
