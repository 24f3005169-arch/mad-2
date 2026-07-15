const { createApp } = Vue;

createApp({
  data(){return{
    user:null, loading:true, view:'dashboard', message:'', error:'',
    loginForm:{email:'',password:''}, registerForm:{name:'',email:'',password:'',phone:''}, authMode:'login',
    treks:[], users:[], bookings:[], notifications:[], stats:{}, staffTreks:[], participants:[],
    filters:{location:'',difficulty:'',duration:''},
    trekForm:{name:'',location:'',difficulty:'Easy',duration_days:1,total_slots:10,status:'Open',start_date:'',end_date:'',description:'',assigned_staff_id:''},
    staffForm:{name:'',email:'',password:'',phone:'',specialization:''},
    profile:{name:'',phone:''}, exportJob:null
  }},
  computed:{
    role(){return this.user?.role},
    navItems(){
      if(this.role==='admin') return [['dashboard','Dashboard','speedometer2'],['treks','Treks','mountain'],['people','Users & Staff','people'],['bookings','Bookings','calendar-check'],['reports','Reports','bar-chart']];
      if(this.role==='staff') return [['dashboard','Dashboard','speedometer2'],['assigned','Assigned Treks','map'],['profile','Profile','person']];
      return [['dashboard','Discover Treks','compass'],['bookings','My Bookings','calendar-check'],['notifications','Notifications','bell'],['profile','Profile','person']];
    }
  },
  methods:{
    async api(url, options={}){
      const res=await fetch(url,{headers:{'Content-Type':'application/json',...(options.headers||{})},...options});
      const data=await res.json().catch(()=>({}));
      if(!res.ok) throw new Error(data.message||'Request failed');
      return data;
    },
    flash(msg,err=false){this.message=err?'':msg;this.error=err?msg:'';setTimeout(()=>{this.message='';this.error=''},3500)},
    async init(){
      try{const d=await this.api('/api/me');this.user=d.user;if(this.user){this.profile={name:this.user.name,phone:this.user.phone};await this.loadDashboard()}}
      catch(e){this.flash(e.message,true)}finally{this.loading=false}
    },
    async login(){try{const d=await this.api('/api/login',{method:'POST',body:JSON.stringify(this.loginForm)});this.user=d.user;this.profile={name:this.user.name,phone:this.user.phone};await this.loadDashboard()}catch(e){this.flash(e.message,true)}},
    async register(){try{const d=await this.api('/api/register',{method:'POST',body:JSON.stringify(this.registerForm)});this.user=d.user;this.profile={name:this.user.name,phone:this.user.phone};await this.loadDashboard()}catch(e){this.flash(e.message,true)}},
    async logout(){await this.api('/api/logout',{method:'POST'});this.user=null;this.view='dashboard'},
    async selectView(v){this.view=v;if(v==='treks'||(v==='dashboard'&&this.role==='user')) await this.loadTreks(this.role==='admin');if(v==='treks'&&this.role==='admin')await this.loadUsers();if(v==='people')await this.loadUsers();if(v==='bookings')await this.loadBookings();if(v==='assigned'||(v==='dashboard'&&this.role==='staff'))await this.loadStaffTreks();if(v==='notifications')await this.loadNotifications()},
    async loadDashboard(){
      if(this.role==='admin'){this.stats=(await this.api('/api/admin/stats')).stats;await this.loadTreks(true)}
      else if(this.role==='staff'){await this.loadStaffTreks()}
      else await this.loadTreks();
    },
    async loadTreks(all=false){
      const p=new URLSearchParams();if(all)p.set('all','1');if(this.filters.location)p.set('location',this.filters.location);if(this.filters.difficulty)p.set('difficulty',this.filters.difficulty);if(this.filters.duration)p.set('duration',this.filters.duration);
      this.treks=(await this.api('/api/treks?'+p.toString())).treks;
    },
    async loadUsers(){this.users=(await this.api('/api/admin/users')).users},
    async loadBookings(){this.bookings=(await this.api(this.role==='admin'?'/api/admin/bookings':'/api/bookings/mine')).bookings},
    async loadStaffTreks(){this.staffTreks=(await this.api('/api/staff/treks')).treks},
    async loadNotifications(){this.notifications=(await this.api('/api/notifications')).notifications},
    async createTrek(){try{await this.api('/api/admin/treks',{method:'POST',body:JSON.stringify(this.trekForm)});this.flash('Trek created');this.trekForm={name:'',location:'',difficulty:'Easy',duration_days:1,total_slots:10,status:'Open',start_date:'',end_date:'',description:'',assigned_staff_id:''};await this.loadTreks(true);await this.loadDashboard()}catch(e){this.flash(e.message,true)}},
    async deleteTrek(id){if(!confirm('Delete this trek?'))return;try{await this.api('/api/admin/treks/'+id,{method:'DELETE'});await this.loadTreks(true);this.flash('Trek deleted')}catch(e){this.flash(e.message,true)}},
    async createStaff(){try{await this.api('/api/admin/staff',{method:'POST',body:JSON.stringify(this.staffForm)});this.flash('Staff account created');this.staffForm={name:'',email:'',password:'',phone:'',specialization:''};await this.loadUsers()}catch(e){this.flash(e.message,true)}},
    async toggleStatus(u){try{await this.api(`/api/admin/users/${u.id}/status`,{method:'PATCH',body:JSON.stringify({status:u.status==='active'?'blacklisted':'active'})});await this.loadUsers()}catch(e){this.flash(e.message,true)}},
    async book(trek){try{await this.api('/api/bookings/'+trek.id,{method:'POST'});this.flash('Booking confirmed');await this.loadTreks()}catch(e){this.flash(e.message,true)}},
    async cancel(b){try{await this.api('/api/bookings/'+b.id+'/cancel',{method:'POST'});await this.loadBookings();this.flash('Booking cancelled')}catch(e){this.flash(e.message,true)}},
    async staffUpdate(t){try{await this.api('/api/staff/treks/'+t.id,{method:'PATCH',body:JSON.stringify({status:t.status,available_slots:t.available_slots})});this.flash('Trek updated');await this.loadStaffTreks()}catch(e){this.flash(e.message,true)}},
    async showParticipants(t){this.participants=(await this.api(`/api/staff/treks/${t.id}/participants`)).participants;this.view='participants'},
    async saveProfile(){try{const d=await this.api('/api/profile',{method:'PATCH',body:JSON.stringify(this.profile)});this.user=d.user;this.flash('Profile updated')}catch(e){this.flash(e.message,true)}},
    async startExport(){try{const d=await this.api('/api/exports',{method:'POST'});this.exportJob=d.job;this.flash('Export started in background');this.pollExport()}catch(e){this.flash('Start Redis and Celery worker before exporting. '+e.message,true)}},
    async pollExport(){if(!this.exportJob)return;const d=await this.api('/api/exports/'+this.exportJob.id);this.exportJob=d.job;if(!['Completed','Failed'].includes(this.exportJob.status))setTimeout(()=>this.pollExport(),2000)},
    async runReport(){try{await this.api('/api/admin/run-monthly-report',{method:'POST'});this.flash('Monthly report job queued')}catch(e){this.flash('Start Redis and Celery worker first. '+e.message,true)}}
  },
  mounted(){this.init()},
  template:`
  <div v-if="loading" class="auth-wrap"><div class="spinner-border text-success"></div></div>
  <div v-else-if="!user" class="auth-wrap">
    <div class="auth-card row g-0">
      <div class="col-md-6 auth-side"><h1 class="display-5 fw-bold">SummitFlow</h1><p class="lead">Simple trekking management for administrators, staff and trekkers.</p><div class="mt-5"><p><i class="bi bi-check-circle me-2"></i>Role-based access</p><p><i class="bi bi-check-circle me-2"></i>Slot-safe booking</p><p><i class="bi bi-check-circle me-2"></i>Redis cache & Celery jobs</p></div></div>
      <div class="col-md-6 auth-form">
        <h2>{{authMode==='login'?'Welcome back':'Create trekker account'}}</h2><p class="muted">Admin and staff use login only.</p>
        <div v-if="error" class="alert alert-danger">{{error}}</div>
        <template v-if="authMode==='login'">
          <input v-model="loginForm.email" class="form-control mb-3" placeholder="Email"><input v-model="loginForm.password" type="password" class="form-control mb-3" placeholder="Password"><button @click="login" class="btn btn-brand w-100">Login</button>
          <button @click="authMode='register'" class="btn btn-link w-100 mt-2">New trekker? Register</button>
        </template>
        <template v-else>
          <input v-model="registerForm.name" class="form-control mb-2" placeholder="Full name"><input v-model="registerForm.email" class="form-control mb-2" placeholder="Email"><input v-model="registerForm.phone" class="form-control mb-2" placeholder="Phone"><input v-model="registerForm.password" type="password" class="form-control mb-3" placeholder="Password (6+ characters)"><button @click="register" class="btn btn-brand w-100">Register</button><button @click="authMode='login'" class="btn btn-link w-100 mt-2">Back to login</button>
        </template>
      </div>
    </div>
  </div>
  <div v-else class="app-shell">
    <aside class="sidebar"><div class="brand mb-4"><i class="bi bi-mountain me-2"></i>SummitFlow</div><div class="small text-white-50 mb-3">{{user.name}} · {{user.role}}</div><button v-for="n in navItems" :key="n[0]" @click="selectView(n[0])" class="nav-btn" :class="{active:view===n[0]}"><i :class="'bi bi-'+n[2]" class="me-2"></i>{{n[1]}}</button><button @click="logout" class="nav-btn mt-4"><i class="bi bi-box-arrow-right me-2"></i>Logout</button></aside>
    <main class="main">
      <div v-if="message" class="alert alert-success">{{message}}</div><div v-if="error" class="alert alert-danger">{{error}}</div>
      <div class="hero mb-4"><h2 class="mb-1">{{view==='dashboard'?'Dashboard':navItems.find(n=>n[0]===view)?.[1]||'Details'}}</h2><p class="mb-0 opacity-75">Trekking Management Application — MAD II</p></div>

      <template v-if="role==='admin' && view==='dashboard'">
        <div class="row g-3"><div v-for="(v,k) in stats" class="col-md"><div class="card stat"><span class="muted text-capitalize">{{k}}</span><strong class="d-block">{{v}}</strong></div></div></div>
      </template>

      <template v-if="(role==='user'&&view==='dashboard') || (role==='admin'&&view==='treks')">
        <div v-if="role==='user'" class="card p-3 mb-3"><div class="row g-2"><div class="col-md"><input v-model="filters.location" class="form-control" placeholder="Location"></div><div class="col-md"><select v-model="filters.difficulty" class="form-select"><option value="">All difficulties</option><option>Easy</option><option>Moderate</option><option>Hard</option></select></div><div class="col-md"><input v-model="filters.duration" type="number" class="form-control" placeholder="Max duration"></div><div class="col-md-auto"><button @click="loadTreks" class="btn btn-brand">Search</button></div></div></div>
        <div v-if="role==='admin'" class="card p-4 mb-4"><h5>Create trek</h5><div class="row g-2"><div class="col-md-4"><input v-model="trekForm.name" class="form-control" placeholder="Trek name"></div><div class="col-md-4"><input v-model="trekForm.location" class="form-control" placeholder="Location"></div><div class="col-md-2"><select v-model="trekForm.difficulty" class="form-select"><option>Easy</option><option>Moderate</option><option>Hard</option></select></div><div class="col-md-2"><input v-model.number="trekForm.duration_days" type="number" class="form-control" placeholder="Days"></div><div class="col-md-3"><input v-model.number="trekForm.total_slots" type="number" class="form-control" placeholder="Slots"></div><div class="col-md-3"><input v-model="trekForm.start_date" type="date" class="form-control"></div><div class="col-md-3"><input v-model="trekForm.end_date" type="date" class="form-control"></div><div class="col-md-3"><select v-model="trekForm.assigned_staff_id" class="form-select"><option value="">No staff</option><option v-for="u in users.filter(x=>x.role==='staff')" :value="u.id">{{u.name}}</option></select></div><div class="col-12"><textarea v-model="trekForm.description" class="form-control" placeholder="Description"></textarea></div><div><button @click="createTrek" class="btn btn-brand">Create Trek</button></div></div></div>
        <div class="row g-3"><div v-for="t in treks" :key="t.id" class="col-md-6 col-xl-4"><div class="card trek-card p-4"><div class="d-flex justify-content-between"><h5>{{t.name}}</h5><span class="badge badge-open">{{t.status}}</span></div><p class="muted mb-2"><i class="bi bi-geo-alt"></i> {{t.location}}</p><p>{{t.difficulty}} · {{t.duration_days}} days · {{t.available_slots}}/{{t.total_slots}} slots</p><p class="small muted">{{t.start_date}} to {{t.end_date}}</p><button v-if="role==='user'" @click="book(t)" class="btn btn-brand">Book Trek</button><button v-if="role==='admin'" @click="deleteTrek(t.id)" class="btn btn-outline-danger">Delete</button></div></div></div>
      </template>

      <template v-if="role==='admin'&&view==='people'">
        <div class="card p-4 mb-4"><h5>Add trek staff</h5><div class="row g-2"><div class="col-md"><input v-model="staffForm.name" class="form-control" placeholder="Name"></div><div class="col-md"><input v-model="staffForm.email" class="form-control" placeholder="Email"></div><div class="col-md"><input v-model="staffForm.password" type="password" class="form-control" placeholder="Temporary password"></div><div class="col-md"><input v-model="staffForm.specialization" class="form-control" placeholder="Specialization"></div><div class="col-md-auto"><button @click="createStaff" class="btn btn-brand">Add Staff</button></div></div></div>
        <div class="card p-3"><table class="table"><thead><tr><th>ID</th><th>Name</th><th>Role</th><th>Email</th><th>Status</th><th></th></tr></thead><tbody><tr v-for="u in users"><td>{{u.id}}</td><td>{{u.name}}</td><td>{{u.role}}</td><td>{{u.email}}</td><td>{{u.status}}</td><td><button @click="toggleStatus(u)" class="btn btn-sm btn-outline-secondary">{{u.status==='active'?'Blacklist':'Activate'}}</button></td></tr></tbody></table></div>
      </template>

      <template v-if="view==='bookings'">
        <div class="card p-3"><div class="d-flex justify-content-between mb-3"><h5>Booking records</h5><button v-if="role==='user'" @click="startExport" class="btn btn-outline-success">Export CSV</button></div><div v-if="exportJob" class="alert alert-info">Export status: {{exportJob.status}} <a v-if="exportJob.status==='Completed'" :href="'/api/exports/'+exportJob.id+'/download'">Download</a></div><table class="table"><thead><tr><th>Trek</th><th>User</th><th>Date</th><th>Status</th><th></th></tr></thead><tbody><tr v-for="b in bookings"><td>{{b.trek_name}}</td><td>{{b.user_name}}</td><td>{{b.start_date}}</td><td>{{b.status}}</td><td><button v-if="role==='user'&&b.status==='Booked'" @click="cancel(b)" class="btn btn-sm btn-outline-danger">Cancel</button></td></tr></tbody></table></div>
      </template>

      <template v-if="role==='staff'&&(view==='dashboard'||view==='assigned')">
        <div class="row g-3"><div v-for="t in staffTreks" class="col-md-6"><div class="card p-4"><h5>{{t.name}}</h5><p>{{t.location}} · {{t.registered_users}} registered</p><div class="row g-2"><div class="col"><select v-model="t.status" class="form-select"><option>Open</option><option>Closed</option><option>Started</option><option>Completed</option></select></div><div class="col"><input v-model.number="t.available_slots" type="number" class="form-control"></div></div><div class="mt-3"><button @click="staffUpdate(t)" class="btn btn-brand me-2">Save</button><button @click="showParticipants(t)" class="btn btn-outline-secondary">Participants</button></div></div></div></div>
      </template>

      <template v-if="view==='participants'"><div class="card p-3"><button @click="view='assigned'" class="btn btn-link">← Back</button><table class="table"><thead><tr><th>Name</th><th>Booking date</th><th>Status</th></tr></thead><tbody><tr v-for="p in participants"><td>{{p.user_name}}</td><td>{{p.booking_date}}</td><td>{{p.status}}</td></tr></tbody></table></div></template>
      <template v-if="view==='notifications'"><div class="card p-3"><div v-for="n in notifications" class="border-bottom py-3"><div>{{n.message}}</div><small class="muted">{{n.created_at}}</small></div><p v-if="!notifications.length" class="muted">No notifications yet.</p></div></template>
      <template v-if="view==='profile'"><div class="card p-4" style="max-width:650px"><h5>Edit profile</h5><input v-model="profile.name" class="form-control mb-3" placeholder="Name"><input v-model="profile.phone" class="form-control mb-3" placeholder="Phone"><button @click="saveProfile" class="btn btn-brand">Save</button></div></template>
      <template v-if="role==='admin'&&view==='reports'"><div class="card p-4"><h5>Monthly activity report</h5><p class="muted">Celery Beat generates this automatically on the first day of each month. You can also trigger it manually.</p><button @click="runReport" class="btn btn-brand">Generate report now</button></div></template>
    </main>
  </div>`
}).mount('#app');
