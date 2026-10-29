/**
 * ParcelDesk - Frontend Application Logic
 * Theme: Carbon + Signal Orange (Industrial Logistics Management)
 * Integrates 3-Tier Architecture, RBAC, OTP Handover, and Analytics
 */

let currentUser = null;
let allStudentsList = [];
let allGuardParcels = [];
let timerIntervals = {};

// Initialize application on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    checkCurrentUser();
});

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
            // Default demo auto-login as gate guard for immediate exploration
            await demoLogin('guard1', 'guard123');
        }
    } catch (err) {
        console.error('Session check failed:', err);
        showToast('Failed to connect to backend API.', 'error');
    }
}

function setUserState(user) {
    currentUser = user;

    // Update navbar badge
    document.getElementById('auth-logged-out').classList.add('hidden');
    document.getElementById('auth-logged-in').classList.remove('hidden');

    const rolePill = document.getElementById('user-role-pill');
    rolePill.textContent = user.role.toUpperCase();
    rolePill.className = `role-badge ${user.role}`;

    document.getElementById('user-display-name').textContent = user.full_name;

    // Update Sidebar role indicator
    const sidebarRoleText = document.getElementById('sidebar-role-name');
    const topbarContextTitle = document.getElementById('topbar-context-title');

    // Hide all role views first
    document.getElementById('guard-view').classList.add('hidden');
    document.getElementById('student-view').classList.add('hidden');
    document.getElementById('warden-view').classList.add('hidden');

    // Hide all sidebar nav sections
    document.getElementById('sidebar-section-guard').classList.add('hidden');
    document.getElementById('sidebar-section-student').classList.add('hidden');
    document.getElementById('sidebar-section-warden').classList.add('hidden');

    // Display view matching user role
    if (user.role === 'guard') {
        document.getElementById('guard-view').classList.remove('hidden');
        document.getElementById('sidebar-section-guard').classList.remove('hidden');
        if (sidebarRoleText) sidebarRoleText.textContent = 'GATE STAFF';
        if (topbarContextTitle) topbarContextTitle.textContent = 'GATE OPERATIONS CONSOLE';
        loadGuardParcels();
        loadStudentsDropdown();
    } else if (user.role === 'student') {
        document.getElementById('student-view').classList.remove('hidden');
        document.getElementById('sidebar-section-student').classList.remove('hidden');
        if (sidebarRoleText) sidebarRoleText.textContent = 'STUDENT RESIDENT';
        if (topbarContextTitle) topbarContextTitle.textContent = 'STUDENT DELIVERY PORTAL';
        document.getElementById('student-portal-name').textContent = user.full_name;
        if (user.student_profile) {
            document.getElementById('student-portal-details').textContent = 
                `Roll No: ${user.student_profile.student_roll_no} | Room: ${user.student_profile.room_no} | ${user.student_profile.hostel_name}`;
        }
        loadStudentDeliveries();
        loadStudentNotifications();
    } else if (user.role === 'warden' || user.role === 'admin') {
        document.getElementById('warden-view').classList.remove('hidden');
        document.getElementById('sidebar-section-warden').classList.remove('hidden');
        if (sidebarRoleText) sidebarRoleText.textContent = user.role === 'admin' ? 'SYSTEM ADMIN' : 'CHIEF WARDEN';
        if (topbarContextTitle) topbarContextTitle.textContent = 'LOGISTICS ANALYTICS & AUDIT';
        loadWardenDashboard();
        loadAuditLogs();
    }
}

async function demoLogin(username, password) {
    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (res.ok) {
            showToast(`Switched persona to ${data.user.full_name} (${data.user.role})`, 'success');
            setUserState(data.user);
        } else {
            showToast(data.error || 'Login failed', 'error');
        }
    } catch (err) {
        showToast('Error connecting to authentication endpoint.', 'error');
    }
}

async function handleLogout() {
    try {
        await fetch('/api/logout', { method: 'POST' });
        currentUser = null;
        document.getElementById('auth-logged-in').classList.add('hidden');
        document.getElementById('auth-logged-out').classList.remove('hidden');
        showToast('Signed out of terminal.', 'info');
        // Switch back to guard demo
        demoLogin('guard1', 'guard123');
    } catch (err) {
        console.error('Logout error:', err);
    }
}

// -------------------------------------------------------------
// Sidebar & Navigation Controls
// -------------------------------------------------------------
function toggleSidebar() {
    const sidebar = document.getElementById('app-sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    sidebar.classList.toggle('open');
    backdrop.classList.toggle('active');
}

function activateNav(linkElem) {
    const parentSection = linkElem.closest('.nav-section');
    if (parentSection) {
        parentSection.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    }
    linkElem.classList.add('active');
    // If on mobile, close sidebar
    if (window.innerWidth <= 900) {
        toggleSidebar();
    }
}

// -------------------------------------------------------------
// Gate Guard Console Functionality
// -------------------------------------------------------------
async function loadGuardParcels() {
    try {
        const res = await fetch('/api/parcels');
        const data = await res.json();
        if (res.ok) {
            allGuardParcels = data.parcels || [];
            renderGuardParcels(allGuardParcels);
            updateGuardKPIs(allGuardParcels);
        }
    } catch (err) {
        console.error('Failed to load guard parcels:', err);
    }
}

function updateGuardKPIs(parcels) {
    const pending = parcels.filter(p => p.status === 'received' || p.status === 'notified').length;
    const collected = parcels.filter(p => p.status === 'collected').length;
    
    // Count logged today
    const todayStr = new Date().toISOString().slice(0, 10);
    const todayCount = parcels.filter(p => p.received_at && p.received_at.startsWith(todayStr)).length;

    document.getElementById('guard-pending-count').textContent = pending;
    document.getElementById('guard-today-count').textContent = todayCount;
    document.getElementById('guard-collected-count').textContent = collected;

    // Sidebar badge
    const sbBadge = document.getElementById('sidebar-guard-pending-count');
    if (sbBadge) sbBadge.textContent = pending;
}

function renderGuardParcels(parcels) {
    const tbody = document.getElementById('guard-parcels-tbody');
    tbody.innerHTML = '';

    if (!parcels || parcels.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center empty-state">No parcels logged in terminal ledger.</td></tr>`;
        return;
    }

    parcels.forEach(p => {
        const tr = document.createElement('tr');

        // Waiting time calculation
        const recDate = new Date(p.received_at);
        const diffHrs = Math.max(0, Math.round((new Date() - recDate) / (1000 * 60 * 60) * 10) / 10);

        // Status badge
        const badgeClass = p.status === 'collected' ? 'badge-collected' : (p.status === 'notified' ? 'badge-notified' : 'badge-received');
        
        // Photo preview thumbnail
        const photoHtml = p.photo_url 
            ? `<img src="${p.photo_url}" class="table-photo-thumb" alt="Parcel Photo" onclick="viewPhoto('${p.photo_url}', '${p.tracking_number}')" title="Click to view photo">`
            : `<span style="color:var(--text-muted);font-size:0.75rem;font-family:var(--font-mono);">NONE</span>`;

        // Action buttons
        let actionsHtml = '';
        if (p.status !== 'collected') {
            actionsHtml = `
                <div style="display:flex;gap:0.4rem;">
                    <button class="btn btn-primary btn-sm" onclick="openHandoverModal(${p.id})">🔑 Hand Over</button>
                    <button class="btn btn-secondary btn-sm" onclick="triggerNotify(${p.id})" title="Resend Notification">🔔</button>
                </div>
            `;
        } else {
            actionsHtml = `<span class="badge badge-collected">✓ Handed Over</span>`;
        }

        tr.innerHTML = `
            <td>
                <strong>${escapeHtml(p.courier_name)}</strong>
                <div style="font-family:var(--font-mono);font-size:0.75rem;color:var(--orange);margin-top:0.15rem;">${escapeHtml(p.tracking_number)}</div>
            </td>
            <td>
                <strong>${escapeHtml(p.student_name)}</strong>
                <div style="font-size:0.75rem;color:var(--text-muted);font-family:var(--font-mono);">${escapeHtml(p.student_roll_no)}</div>
            </td>
            <td>
                <div>${escapeHtml(p.hostel_name)} (${escapeHtml(p.hostel_code)})</div>
                <div style="font-size:0.75rem;color:var(--text-muted);font-family:var(--font-mono);">${escapeHtml(p.room_no)}</div>
            </td>
            <td style="font-family:var(--font-mono);font-size:0.78rem;">${formatDate(p.received_at)}</td>
            <td style="font-family:var(--font-mono);font-size:0.78rem;">${p.status === 'collected' ? '-' : `${diffHrs} hrs`}</td>
            <td>${photoHtml}</td>
            <td><span class="badge ${badgeClass}">${p.status}</span></td>
            <td>${actionsHtml}</td>
        `;
        tbody.appendChild(tr);
    });
}

function filterGuardTable() {
    const q = document.getElementById('guard-search-input').value.toLowerCase().trim();
    if (!q) {
        renderGuardParcels(allGuardParcels);
        return;
    }
    const filtered = allGuardParcels.filter(p => {
        return (p.tracking_number && p.tracking_number.toLowerCase().includes(q)) ||
               (p.student_name && p.student_name.toLowerCase().includes(q)) ||
               (p.courier_name && p.courier_name.toLowerCase().includes(q)) ||
               (p.room_no && p.room_no.toLowerCase().includes(q)) ||
               (p.student_roll_no && p.student_roll_no.toLowerCase().includes(q));
    });
    renderGuardParcels(filtered);
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
    btn.querySelector('span').textContent = 'Uploading & Saving...';

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
            showToast(`Parcel logged! One-time code generated and student notified.`, 'success');
            loadGuardParcels();
        } else {
            showToast(data.error || 'Failed to log parcel', 'error');
        }
    } catch (err) {
        showToast('Error uploading parcel to server.', 'error');
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
            showToast('Notification re-sent to student!', 'success');
            loadGuardParcels();
        } else {
            showToast(data.error || 'Notification failed', 'error');
        }
    } catch (err) {
        showToast('Network error triggering notification', 'error');
    }
}

// -------------------------------------------------------------
// Handover & OTP Verification (ACID Transaction)
// -------------------------------------------------------------
function openHandoverModal(preselectedParcelId = null) {
    const select = document.getElementById('handover-parcel-select');
    select.innerHTML = '<option value="">-- Choose parcel to verify --</option>';

    // Filter pending parcels
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
            <strong>Recipient:</strong> ${escapeHtml(parcel.student_name)} (${escapeHtml(parcel.student_roll_no)})<br>
            <strong>Hostel / Room:</strong> ${escapeHtml(parcel.hostel_name)} - ${escapeHtml(parcel.room_no)}<br>
            <strong>Courier:</strong> ${escapeHtml(parcel.courier_name)} (<span style="color:var(--orange);font-family:var(--font-mono);">${escapeHtml(parcel.tracking_number)}</span>)
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
        showToast('Please select parcel and enter the 6-digit OTP.', 'error');
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
            showToast('✓ OTP Verified! Handover transaction recorded and parcel released.', 'success');
            loadGuardParcels();
        } else {
            showToast(data.error || 'Handover verification failed', 'error');
        }
    } catch (err) {
        showToast('Network error executing handover transaction.', 'error');
    } finally {
        btn.disabled = false;
        btn.querySelector('span').textContent = 'Verify & Release Parcel';
    }
}

// -------------------------------------------------------------
// Student Portal Deliveries & OTP Display
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

    if (!parcels || parcels.length === 0) {
        container.innerHTML = `<div class="empty-state">No parcels registered for your room yet.</div>`;
        return;
    }

    parcels.forEach(p => {
        const card = document.createElement('div');
        card.className = 'student-parcel-card';

        const isCollected = p.status === 'collected';
        const isNotified = p.status === 'notified';

        // Stepper state
        const s1Active = 'completed';
        const s2Active = isNotified || isCollected ? 'completed' : 'active';
        const s3Active = isCollected ? 'completed' : '';

        // Dynamic OTP display or handover confirmation
        let otpSection = '';
        if (!isCollected) {
            otpSection = `
                <div class="otp-showcase">
                    <div class="otp-box-left">
                        <span class="otp-tag">COLLECTION PASSCODE (SHOW AT GATE)</span>
                        <div class="otp-digits" id="otp-display-${p.id}">••••••</div>
                        <span class="otp-expiry" id="otp-timer-${p.id}">Single-use cryptographic hash</span>
                    </div>
                    <div>
                        <button class="btn btn-primary btn-sm" onclick="requestStudentOtp(${p.id})">🔑 View / Refresh OTP</button>
                    </div>
                </div>
            `;
        } else {
            otpSection = `
                <div style="background:var(--success-subtle);border:1px solid var(--success-border);padding:0.75rem 1rem;border-radius:var(--radius-sm);color:var(--success);font-size:0.84rem;display:flex;align-items:center;gap:0.5rem;font-family:var(--font-mono);">
                    <span>✓ Collected and verified on ${formatDate(p.collected_at || p.handover_time)}</span>
                </div>
            `;
        }

        // Photo thumbnail
        const photoSection = p.photo_url ? `
            <div style="margin-top:0.5rem;">
                <span style="font-size:0.72rem;font-family:var(--font-mono);color:var(--text-muted);display:block;margin-bottom:0.25rem;">PACKAGE PHOTO (AZURE BLOB):</span>
                <img src="${p.photo_url}" class="table-photo-thumb" style="width:64px;height:64px;" onclick="viewPhoto('${p.photo_url}', '${p.tracking_number}')" title="Click to view full photo">
            </div>
        ` : '';

        card.innerHTML = `
            <div class="parcel-top">
                <div>
                    <div class="parcel-title">${escapeHtml(p.courier_name)}</div>
                    <div class="parcel-meta">Tracking: <strong style="color:var(--orange);font-family:var(--font-mono);">${escapeHtml(p.tracking_number)}</strong> | Received: ${formatDate(p.received_at)}</div>
                    ${p.remarks ? `<div style="font-size:0.8rem;color:var(--text-secondary);margin-top:0.25rem;">Note: ${escapeHtml(p.remarks)}</div>` : ''}
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
            showToast('Fresh OTP generated and hashed with SHA-256 in database.', 'success');
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
            const feed = document.getElementById('student-notifications-feed');
            feed.innerHTML = '';
            const notifs = data.notifications || [];

            if (notifs.length === 0) {
                feed.innerHTML = `<div class="empty-state">No notifications.</div>`;
                return;
            }

            notifs.forEach(n => {
                const card = document.createElement('div');
                card.className = 'notif-card';
                card.onclick = () => viewJsonPayload(n.payload);

                card.innerHTML = `
                    <div class="notif-card-header">
                        <span>📦 ${escapeHtml(n.courier_name)} Arrived</span>
                        <span class="notif-time">${formatDate(n.sent_at)}</span>
                    </div>
                    <p style="color:var(--text-secondary);font-size:0.8rem;">
                        ${n.payload && n.payload.message ? escapeHtml(n.payload.message) : `Parcel ${n.tracking_number} received.`}
                    </p>
                    <div style="font-size:0.72rem;color:var(--orange);margin-top:0.4rem;font-weight:700;font-family:var(--font-mono);">
                        🔍 Click to view DP-900 JSON Document
                    </div>
                `;
                feed.appendChild(card);
            });
        }
    } catch (err) {
        console.error('Failed to load notifications:', err);
    }
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

            // Render Hostel breakdown bars
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
        container.innerHTML = '<div class="empty-state">No hostel data available.</div>';
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
                <span style="color:var(--orange);font-family:var(--font-mono);font-weight:700;">${count} parcels</span>
            </div>
            <div class="dist-bar-track">
                <div class="dist-bar-fill" style="width: ${Math.max(percentage, 5)}%"></div>
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
                    <td><strong style="color:var(--orange);font-family:var(--font-mono);">${escapeHtml(l.action)}</strong></td>
                    <td>${escapeHtml(l.full_name || l.username || 'System')}</td>
                    <td><span class="role-badge ${l.role || 'guard'}">${escapeHtml(l.role || 'system')}</span></td>
                    <td style="font-family:var(--font-mono);font-size:0.75rem;color:var(--text-muted);">${escapeHtml(l.ip_address || '127.0.0.1')}</td>
                    <td style="font-size:0.8rem;color:var(--text-secondary);max-width:300px;word-break:break-all;">${escapeHtml(l.details || '-')}</td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (err) {
        console.error('Failed to load audit logs:', err);
    }
}

// -------------------------------------------------------------
// Modals, Photo Viewer & JSON Payloads
// -------------------------------------------------------------
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
        toast.style.transition = 'opacity 0.4s';
        setTimeout(() => toast.remove(), 400);
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
