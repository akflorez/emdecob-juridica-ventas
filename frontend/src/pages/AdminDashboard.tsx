import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { Plus, Users, Building2, ShieldAlert } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { apiFetch, getBillingTiers, getBillingSimulator, updateBillingTiers, BillingTier, BillingSimulatorResult } from '@/services/api';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { DollarSign, Save, RefreshCw, MoreHorizontal, Edit, Check, AlertTriangle } from 'lucide-react';
import { Textarea } from '@/components/ui/textarea';

export default function AdminDashboard() {
  const { user } = useAuth();
  const { toast } = useToast();
  
  const [companies, setCompanies] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [tiers, setTiers] = useState<BillingTier[]>([]);
  const [simulatorData, setSimulatorData] = useState<BillingSimulatorResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingTiers, setSavingTiers] = useState(false);

  const getCompanyName = (companyId: number | null) => {
    if (!companyId) return 'Global (SuperAdmin)';
    const comp = companies.find(c => c.id === companyId);
    return comp ? comp.nombre : `Empresa #${companyId}`;
  };

  // Modals Open State
  const [isCompanyModalOpen, setIsCompanyModalOpen] = useState(false);
  const [isUserModalOpen, setIsUserModalOpen] = useState(false);
  const [suspendModalOpen, setSuspendModalOpen] = useState(false);
  
  // Edit State
  const [editingCompany, setEditingCompany] = useState<any>(null);
  const [isEditCompanyModalOpen, setIsEditCompanyModalOpen] = useState(false);
  const [editCompanyForm, setEditCompanyForm] = useState({ nombre: '', nit: '', limite_usuarios: 5, logo_base64: '' });

  const [editingUser, setEditingUser] = useState<any>(null);
  const [isEditUserModalOpen, setIsEditUserModalOpen] = useState(false);
  const [editUserForm, setEditUserForm] = useState({
    nombre: '',
    email: '',
    role: 'USER',
    cases_view_scope: 'OWN',
    password: '',
    company_id: '',
    sync_with_clickup: true,
    clickup_api_token: ''
  });

  // Suspend Company State
  const [suspendCompanyId, setSuspendCompanyId] = useState<number | null>(null);
  const [suspendReason, setSuspendReason] = useState("");
  const [suspendNotes, setSuspendNotes] = useState("");

  // Create Forms State
  const [newCompany, setNewCompany] = useState({ nombre: '', nit: '', limite_usuarios: 5, logo_base64: '' });
  const [newUser, setNewUser] = useState({
    username: '',
    password: '',
    nombre: '',
    company_id: '',
    email: '',
    is_admin: false,
    role: 'USER',
    cases_view_scope: 'OWN',
    sync_with_clickup: true,
    clickup_api_token: ''
  });

  useEffect(() => {
    if (user?.is_admin || user?.is_superadmin) {
      fetchData();
    }
  }, [user]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [compRes, usrRes, tiersRes, simRes] = await Promise.all([
        apiFetch<any[]>('/api/admin/companies'),
        apiFetch<any[]>('/api/admin/users'),
        getBillingTiers().catch(() => ({ tiers: [] as BillingTier[] })),
        getBillingSimulator().catch(() => ({ simulator: [] as BillingSimulatorResult[] }))
      ]);
      setCompanies(compRes || []);
      setUsers(usrRes || []);
      if (tiersRes && 'tiers' in tiersRes) setTiers(tiersRes.tiers);
      if (simRes && 'simulator' in simRes) setSimulatorData(simRes.simulator);
    } catch (error: any) {
      toast({ title: "Error", description: "No se pudieron cargar los datos.", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCompany = async () => {
    try {
      const res = await apiFetch<any>('/api/admin/companies', {
        method: 'POST',
        body: JSON.stringify(newCompany)
      });
      setCompanies([...companies, res]);
      setIsCompanyModalOpen(false);
      setNewCompany({ nombre: '', nit: '', limite_usuarios: 5, logo_base64: '' });
      toast({ title: "Empresa creada", description: "La empresa se creó correctamente." });
      fetchData(); // reload statistics and simulator
    } catch (e: any) {
      toast({ title: "Error", description: e.message || "No se pudo crear la empresa", variant: "destructive" });
    }
  };

  const handleCreateUser = async () => {
    try {
      const isGlobal = newUser.company_id === 'global' || newUser.company_id === '';
      const payload = {
        username: newUser.username,
        password: newUser.password,
        nombre: newUser.nombre,
        company_id: isGlobal ? null : parseInt(newUser.company_id),
        is_admin: isGlobal || newUser.role === 'COMPANY_ADMIN',
        email: newUser.email || undefined,
        role: isGlobal ? 'SUPERADMIN' : newUser.role,
        cases_view_scope: isGlobal ? 'GLOBAL' : newUser.cases_view_scope,
        sync_with_clickup: newUser.sync_with_clickup,
        clickup_api_token: newUser.clickup_api_token || null
      };
      const res = await apiFetch<any>('/api/admin/users', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      setUsers([...users, res]);
      setIsUserModalOpen(false);
      setNewUser({
        username: '',
        password: '',
        nombre: '',
        company_id: '',
        email: '',
        is_admin: false,
        role: 'USER',
        cases_view_scope: 'OWN',
        sync_with_clickup: true,
        clickup_api_token: ''
      });
      toast({ title: "Usuario creado", description: "El usuario se creó correctamente." });
      fetchData();
    } catch (e: any) {
      toast({ title: "Error", description: e.message || "No se pudo crear el usuario", variant: "destructive" });
    }
  };

  const handleUpdateUser = async (userId: number, data: any) => {
    try {
      await apiFetch<any>(`/api/admin/users/${userId}`, {
        method: 'PUT',
        body: JSON.stringify(data)
      });
      toast({ title: "Usuario actualizado", description: "El usuario se actualizó correctamente." });
      fetchData();
    } catch (e: any) {
      toast({ title: "Error", description: e.message || "No se pudo actualizar el usuario", variant: "destructive" });
    }
  };

  const handleEditUserSubmit = async () => {
    if (!editingUser) return;
    try {
      const isGlobal = editUserForm.company_id === 'global' || editUserForm.company_id === '';
      const payload: any = {
        nombre: editUserForm.nombre,
        email: editUserForm.email || null,
        role: isGlobal ? 'SUPERADMIN' : editUserForm.role,
        cases_view_scope: isGlobal ? 'GLOBAL' : editUserForm.cases_view_scope,
        company_id: isGlobal ? -1 : parseInt(editUserForm.company_id),
        sync_with_clickup: editUserForm.sync_with_clickup,
        clickup_api_token: editUserForm.clickup_api_token || null
      };
      if (editUserForm.password) {
        payload.password = editUserForm.password;
      }
      await apiFetch<any>(`/api/admin/users/${editingUser.id}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
      });
      toast({ title: "Usuario actualizado", description: "El usuario se modificó correctamente." });
      setIsEditUserModalOpen(false);
      setEditingUser(null);
      fetchData();
    } catch (e: any) {
      toast({ title: "Error", description: e.message || "No se pudo actualizar el usuario", variant: "destructive" });
    }
  };

  const handleUpdateCompanyInfo = async (companyId: number, data: any) => {
    try {
      await apiFetch<any>(`/api/admin/companies/${companyId}`, {
        method: 'PUT',
        body: JSON.stringify(data)
      });
      toast({ title: "Empresa actualizada", description: "La empresa se actualizó correctamente." });
      setIsEditCompanyModalOpen(false);
      setEditingCompany(null);
      fetchData();
    } catch (e: any) {
      toast({ title: "Error", description: e.message || "No se pudo actualizar la empresa", variant: "destructive" });
    }
  };

  const handleNewLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setNewCompany(prev => ({ ...prev, logo_base64: reader.result as string }));
      };
      reader.readAsDataURL(file);
    }
  };

  const handleEditLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setEditCompanyForm(prev => ({ ...prev, logo_base64: reader.result as string }));
      };
      reader.readAsDataURL(file);
    }
  };

  const handleInactivateCompany = async (companyId: number) => {
    try {
      await apiFetch<any>(`/api/admin/companies/${companyId}`, {
        method: 'PUT',
        body: JSON.stringify({ estado: 'inactiva' })
      });
      toast({ title: "Empresa Inactivada", description: "La empresa ahora está inactiva." });
      fetchData();
    } catch (e: any) {
      toast({ title: "Error", description: e.message || "No se pudo inactivar la empresa", variant: "destructive" });
    }
  };

  const handleToggleUserActive = async (userId: number, currentActive: boolean) => {
    try {
      await apiFetch<any>(`/api/admin/users/${userId}`, {
        method: 'PUT',
        body: JSON.stringify({ is_active: !currentActive })
      });
      toast({
        title: currentActive ? "Usuario desactivado" : "Usuario activado",
        description: `El usuario ha sido ${currentActive ? 'desactivado' : 'activado'} correctamente.`
      });
      fetchData();
    } catch (e: any) {
      toast({ title: "Error", description: e.message || "No se pudo cambiar el estado del usuario", variant: "destructive" });
    }
  };

  const handleSaveTiers = async () => {
    setSavingTiers(true);
    try {
      await updateBillingTiers(tiers);
      toast({ title: "Rangos actualizados", description: "La configuración de facturación ha sido guardada." });
      
      // Refrescar el simulador con los nuevos rangos
      const simRes = await getBillingSimulator();
      if (simRes && 'simulator' in simRes) {
        setSimulatorData(simRes.simulator);
      }
    } catch (e: any) {
      toast({ title: "Error", description: e.message || "No se pudieron guardar los rangos", variant: "destructive" });
    } finally {
      setSavingTiers(false);
    }
  };

  const handleSuspendCompany = async () => {
    if (!suspendCompanyId || !suspendReason) {
      toast({ title: "Error", description: "El motivo es obligatorio", variant: "destructive" });
      return;
    }
    try {
      await apiFetch(`/api/admin/companies/${suspendCompanyId}/suspend`, {
        method: 'POST',
        body: JSON.stringify({ reason: suspendReason, notes: suspendNotes })
      });
      toast({ title: "Empresa Suspendida", description: "La empresa ha sido suspendida exitosamente." });
      setSuspendModalOpen(false);
      fetchData();
    } catch (e: any) {
      toast({ title: "Error", description: e.message || "No se pudo suspender la empresa", variant: "destructive" });
    }
  };

  const handleReactivateCompany = async (companyId: number) => {
    try {
      await apiFetch(`/api/admin/companies/${companyId}/reactivate`, {
        method: 'POST',
        body: JSON.stringify({ notes: 'Reactivado desde panel Admin' })
      });
      toast({ title: "Empresa Reactivada", description: "La empresa ha sido reactivada." });
      fetchData();
    } catch (e: any) {
      toast({ title: "Error", description: e.message || "No se pudo reactivar la empresa", variant: "destructive" });
    }
  };

  const handleMarkOverdue = async (companyId: number) => {
    try {
      await apiFetch(`/api/admin/companies/${companyId}/mark-overdue`, { method: 'POST' });
      toast({ title: "Marcada en Mora", description: "El estado de pago ha cambiado a en mora." });
      fetchData();
    } catch (e: any) {
      toast({ title: "Error", description: e.message || "No se pudo cambiar el estado", variant: "destructive" });
    }
  };

  const addTier = () => {
    const lastTier = tiers[tiers.length - 1];
    const newMin = lastTier ? (lastTier.max_cases ? lastTier.max_cases + 1 : lastTier.min_cases + 100) : 0;
    setTiers([...tiers, { min_cases: newMin, max_cases: null, price: 0 }]);
  };

  const updateTier = (index: number, field: keyof BillingTier, value: any) => {
    const newTiers = [...tiers];
    if (field === 'max_cases' && value === '') value = null;
    else if (value !== null) value = Number(value);
    newTiers[index] = { ...newTiers[index], [field]: value };
    setTiers(newTiers);
  };

  const removeTier = (index: number) => {
    setTiers(tiers.filter((_, i) => i !== index));
  };

  if (user?.role !== 'SUPERADMIN' && user?.is_superadmin !== true && (!user?.is_admin || user?.company_id)) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <ShieldAlert className="h-16 w-16 text-destructive mb-4 animate-bounce" />
        <h2 className="text-2xl font-bold text-slate-800">Acceso Denegado</h2>
        <p className="text-muted-foreground mt-2">No tienes privilegios de SuperAdmin para ver esta página.</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6 animate-fade-in">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b pb-5">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-blue-700 to-indigo-800 bg-clip-text text-transparent">
            Panel SuperAdmin (SaaS)
          </h1>
          <p className="text-muted-foreground mt-1">
            Administra los inquilinos (empresas) y usuarios globales del sistema.
          </p>
        </div>
      </div>

      <Tabs defaultValue="empresas" className="w-full">
        <TabsList className="mb-6 bg-slate-100/80 p-1 rounded-lg">
          <TabsTrigger value="empresas" className="flex items-center gap-2 px-4 py-2">
            <Building2 className="w-4 h-4" /> Empresas
          </TabsTrigger>
          <TabsTrigger value="usuarios" className="flex items-center gap-2 px-4 py-2">
            <Users className="w-4 h-4" /> Usuarios Globales
          </TabsTrigger>
          <TabsTrigger value="facturacion" className="flex items-center gap-2 px-4 py-2">
            <DollarSign className="w-4 h-4" /> Facturación
          </TabsTrigger>
        </TabsList>

        <TabsContent value="empresas" className="space-y-4">
          <Card className="border-slate-100 shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-xl font-bold text-slate-800">Empresas Inquilinas</CardTitle>
                <CardDescription>Gestión de las cuentas de clientes</CardDescription>
              </div>
              <Button onClick={() => setIsCompanyModalOpen(true)} size="sm" className="bg-blue-600 hover:bg-blue-500">
                <Plus className="w-4 h-4 mr-1" /> Nueva Empresa
              </Button>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="p-8 text-center text-muted-foreground flex flex-col items-center justify-center gap-2">
                  <RefreshCw className="h-8 w-8 animate-spin text-blue-600" />
                  <span>Cargando empresas...</span>
                </div>
              ) : (
                <div className="overflow-x-auto rounded-md border">
                  <Table>
                    <TableHeader className="bg-slate-50/50">
                      <TableRow>
                        <TableHead className="w-[80px]">ID</TableHead>
                        <TableHead>Nombre</TableHead>
                        <TableHead>NIT</TableHead>
                        <TableHead>Estado</TableHead>
                        <TableHead>Límite Usr.</TableHead>
                        <TableHead className="text-center">Casos Validados</TableHead>
                        <TableHead>Est. Pago</TableHead>
                        <TableHead className="w-[100px] text-right">Acciones</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {companies.map(c => (
                        <TableRow key={c.id} className="hover:bg-slate-50/30 transition-colors">
                          <TableCell className="font-mono text-xs">{c.id}</TableCell>
                          <TableCell className="font-semibold text-slate-900">{c.nombre}</TableCell>
                          <TableCell className="text-slate-600 font-mono text-sm">{c.nit || '—'}</TableCell>
                          <TableCell>
                            <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                              c.estado === 'activo' 
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' 
                                : c.estado === 'suspendida_pago' 
                                ? 'bg-rose-50 text-rose-700 border border-rose-200' 
                                : c.estado === 'inactiva' 
                                ? 'bg-slate-100 text-slate-700 border border-slate-200' 
                                : 'bg-yellow-50 text-yellow-700 border border-yellow-200'
                            }`}>
                              {c.estado.toUpperCase()}
                            </span>
                          </TableCell>
                          <TableCell>{c.limite_usuarios}</TableCell>
                          <TableCell className="font-bold text-center text-blue-600">{c.cases_count ?? 0}</TableCell>
                          <TableCell>
                            <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                              c.payment_status === 'al_dia' 
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' 
                                : c.payment_status === 'en_mora' 
                                ? 'bg-yellow-50 text-yellow-700 border border-yellow-200' 
                                : c.payment_status === 'suspendido' 
                                ? 'bg-rose-50 text-rose-700 border border-rose-200' 
                                : 'bg-gray-100 text-gray-700'
                            }`}>
                              {c.payment_status?.toUpperCase() || 'AL_DIA'}
                            </span>
                          </TableCell>
                          <TableCell className="text-right">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" className="h-8 w-8 p-0">
                                  <span className="sr-only">Abrir menú</span>
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-[180px]">
                                <DropdownMenuItem onClick={() => {
                                  setEditingCompany(c);
                                  setEditCompanyForm({
                                    nombre: c.nombre,
                                    nit: c.nit || '',
                                    limite_usuarios: c.limite_usuarios
                                  });
                                  setIsEditCompanyModalOpen(true);
                                }}>
                                  <Edit className="w-4 h-4 mr-2" /> Editar Empresa
                                </DropdownMenuItem>
                                
                                {c.estado !== 'inactiva' && (
                                  <DropdownMenuItem onClick={() => handleInactivateCompany(c.id)} className="text-destructive focus:text-destructive focus:bg-rose-50">
                                    <AlertTriangle className="w-4 h-4 mr-2" /> Inactivar
                                  </DropdownMenuItem>
                                )}

                                {c.estado === 'inactiva' && (
                                  <DropdownMenuItem onClick={() => handleReactivateCompany(c.id)} className="text-emerald-600 focus:text-emerald-600 focus:bg-emerald-50">
                                    <Check className="w-4 h-4 mr-2" /> Reactivar
                                  </DropdownMenuItem>
                                )}
                                
                                {c.estado !== 'suspendida_pago' && c.estado !== 'inactiva' && (
                                  <>
                                    <DropdownMenuItem onClick={() => {
                                      setSuspendCompanyId(c.id);
                                      setSuspendReason("");
                                      setSuspendNotes("");
                                      setSuspendModalOpen(true);
                                    }}>
                                      Suspender por pago
                                    </DropdownMenuItem>
                                    <DropdownMenuItem onClick={() => handleMarkOverdue(c.id)}>
                                      Marcar en mora
                                    </DropdownMenuItem>
                                  </>
                                )}

                                {c.estado === 'suspendida_pago' && (
                                  <DropdownMenuItem onClick={() => handleReactivateCompany(c.id)} className="text-emerald-600 focus:text-emerald-600">
                                    Reactivar
                                  </DropdownMenuItem>
                                )}
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </TableCell>
                        </TableRow>
                      ))}
                      {companies.length === 0 && (
                        <TableRow>
                          <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                            No hay empresas registradas
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="usuarios" className="space-y-4">
          <Card className="border-slate-100 shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-xl font-bold text-slate-800">Usuarios del Sistema</CardTitle>
                <CardDescription>Cuentas globales y asociadas a empresas inquilinas</CardDescription>
              </div>
              <Button onClick={() => setIsUserModalOpen(true)} size="sm" className="bg-blue-600 hover:bg-blue-500">
                <Plus className="w-4 h-4 mr-1" /> Nuevo Usuario
              </Button>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="p-8 text-center text-muted-foreground flex flex-col items-center justify-center gap-2">
                  <RefreshCw className="h-8 w-8 animate-spin text-blue-600" />
                  <span>Cargando usuarios...</span>
                </div>
              ) : (
                <div className="overflow-x-auto rounded-md border">
                  <Table>
                    <TableHeader className="bg-slate-50/50">
                      <TableRow>
                        <TableHead className="w-[80px]">ID</TableHead>
                        <TableHead>Username</TableHead>
                        <TableHead>Nombre</TableHead>
                        <TableHead>Empresa</TableHead>
                        <TableHead>Rol / Alcance</TableHead>
                        <TableHead>Estado</TableHead>
                        <TableHead className="w-[100px] text-right">Acciones</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {users.map(u => (
                        <TableRow key={u.id} className="hover:bg-slate-50/30 transition-colors">
                          <TableCell className="font-mono text-xs">{u.id}</TableCell>
                          <TableCell className="font-mono text-sm font-semibold">{u.username}</TableCell>
                          <TableCell>{u.nombre}</TableCell>
                          <TableCell className="font-medium text-slate-700">{getCompanyName(u.company_id)}</TableCell>
                          <TableCell>
                            <div className="flex flex-col gap-1">
                              <span className={`px-2 py-0.5 rounded-full text-xs font-semibold w-max ${
                                u.role === 'SUPERADMIN' 
                                  ? 'bg-purple-50 text-purple-700 border border-purple-200' 
                                  : u.role === 'COMPANY_ADMIN' 
                                  ? 'bg-blue-50 text-blue-700 border border-blue-200' 
                                  : 'bg-slate-50 text-slate-700 border border-slate-200'
                              }`}>
                                {u.role || 'USER'}
                              </span>
                              <span className="text-[11px] text-muted-foreground ml-1">
                                Alcance: {u.cases_view_scope || 'OWN'}
                              </span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                              u.is_active 
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' 
                                : 'bg-rose-50 text-rose-700 border border-rose-200'
                            }`}>
                              {u.is_active ? 'ACTIVO' : 'INACTIVO'}
                            </span>
                          </TableCell>
                          <TableCell className="text-right">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" className="h-8 w-8 p-0">
                                  <span className="sr-only">Abrir menú</span>
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-[200px]">
                                <DropdownMenuItem onClick={() => {
                                  setEditingUser(u);
                                  setEditUserForm({
                                    nombre: u.nombre || '',
                                    email: u.email || '',
                                    role: u.role || 'USER',
                                    cases_view_scope: u.cases_view_scope || 'OWN',
                                    password: '',
                                    company_id: u.company_id ? u.company_id.toString() : 'global'
                                  });
                                  setIsEditUserModalOpen(true);
                                }}>
                                  <Edit className="w-4 h-4 mr-2" /> Editar Usuario
                                </DropdownMenuItem>

                                {/* Logical Toggle Activar / Desactivar */}
                                {u.id !== user?.id ? (
                                  <DropdownMenuItem 
                                    onClick={() => handleToggleUserActive(u.id, u.is_active)}
                                    className={u.is_active ? "text-destructive focus:text-destructive focus:bg-rose-50" : "text-emerald-600 focus:text-emerald-600 focus:bg-emerald-50"}
                                  >
                                    {u.is_active ? 'Desactivar' : 'Activar'}
                                  </DropdownMenuItem>
                                ) : (
                                  <DropdownMenuItem disabled className="text-muted-foreground cursor-not-allowed">
                                    No puedes desactivarte a ti mismo
                                  </DropdownMenuItem>
                                )}

                                {/* Admin shortcuts */}
                                {u.id !== user?.id && (
                                  <>
                                    <div className="h-px bg-slate-100 my-1" />
                                    {u.role === 'SUPERADMIN' ? (
                                      <DropdownMenuItem onClick={() => handleUpdateUser(u.id, { role: 'USER', cases_view_scope: 'OWN' })}>
                                        Hacer usuario estándar
                                      </DropdownMenuItem>
                                    ) : (
                                      <DropdownMenuItem onClick={() => handleUpdateUser(u.id, { role: 'SUPERADMIN', cases_view_scope: 'GLOBAL' })}>
                                        Hacer SuperAdmin
                                      </DropdownMenuItem>
                                    )}

                                    {u.company_id && (
                                      <DropdownMenuItem onClick={() => handleUpdateUser(u.id, { company_id: -1, role: 'SUPERADMIN', cases_view_scope: 'GLOBAL' })}>
                                        Mover a Global (SuperAdmin)
                                      </DropdownMenuItem>
                                    )}

                                    {companies.map(c => (
                                      c.id !== u.company_id && (
                                        <DropdownMenuItem key={c.id} onClick={() => handleUpdateUser(u.id, { company_id: c.id, role: 'USER', cases_view_scope: 'OWN' })}>
                                          Asignar a {c.nombre} (USER)
                                        </DropdownMenuItem>
                                      )
                                    ))}
                                  </>
                                )}
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </TableCell>
                        </TableRow>
                      ))}
                      {users.length === 0 && (
                        <TableRow>
                          <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                            No hay usuarios registrados
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="facturacion" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1 space-y-6">
              <Card className="border-slate-100 shadow-sm">
                <CardHeader>
                  <CardTitle className="text-lg font-bold text-slate-800 font-sans">Configurar Tarifas</CardTitle>
                  <CardDescription>Define los rangos de cobro por radicados activos</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {tiers.map((tier, idx) => (
                    <div key={idx} className="flex flex-col gap-2 p-3 bg-slate-50/50 rounded-lg border border-slate-150">
                      <div className="flex justify-between items-center border-b pb-1">
                        <span className="text-xs font-bold text-slate-500 font-mono uppercase">Rango {idx + 1}</span>
                        <Button variant="ghost" size="sm" onClick={() => removeTier(idx)} className="h-6 w-6 p-0 text-rose-500 hover:text-rose-700 hover:bg-rose-50/50 font-bold">✕</Button>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="space-y-1">
                          <Label className="text-[10px] text-slate-500 font-bold uppercase">Mínimo</Label>
                          <Input type="number" value={tier.min_cases} onChange={(e) => updateTier(idx, 'min_cases', e.target.value)} className="h-8 text-sm" />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-[10px] text-slate-500 font-bold uppercase">Máximo (vacío = ∞)</Label>
                          <Input type="number" value={tier.max_cases ?? ''} onChange={(e) => updateTier(idx, 'max_cases', e.target.value)} className="h-8 text-sm" placeholder="∞" />
                        </div>
                        <div className="col-span-2 space-y-1 mt-1">
                          <Label className="text-[10px] text-slate-500 font-bold uppercase">Tarifa Fija (COP)</Label>
                          <Input type="number" value={tier.price} onChange={(e) => updateTier(idx, 'price', e.target.value)} className="h-8 text-sm font-semibold text-emerald-600" />
                        </div>
                      </div>
                    </div>
                  ))}
                  <Button variant="outline" className="w-full border-dashed border-slate-300 hover:bg-slate-50" onClick={addTier}>
                    <Plus className="w-4 h-4 mr-2" /> Agregar Rango
                  </Button>
                  <Button className="w-full mt-4 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold" onClick={handleSaveTiers} disabled={savingTiers}>
                    {savingTiers ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                    Guardar y Simular
                  </Button>
                </CardContent>
              </Card>
            </div>

            <div className="lg:col-span-2">
              <Card className="h-full border-slate-100 shadow-sm">
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="text-lg font-bold text-slate-800">Simulador de Facturación</CardTitle>
                    <CardDescription>Impacto de los rangos actuales en las empresas registradas</CardDescription>
                  </div>
                  <Button variant="outline" size="sm" onClick={fetchData}>
                    <RefreshCw className="w-4 h-4 mr-2" /> Actualizar
                  </Button>
                </CardHeader>
                <CardContent>
                  <div className="rounded-md border overflow-x-auto">
                    <Table>
                      <TableHeader className="bg-slate-50/50">
                        <TableRow>
                          <TableHead>Empresa</TableHead>
                          <TableHead className="text-center">Usuarios</TableHead>
                          <TableHead className="text-center">Rad. Activos</TableHead>
                          <TableHead>Rango Aplicado</TableHead>
                          <TableHead className="text-right">A Cobrar (COP)</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {simulatorData.map((d, i) => (
                          <TableRow key={i} className="hover:bg-slate-50/30">
                            <TableCell className="font-semibold text-slate-800">{d.company_name}</TableCell>
                            <TableCell className="text-center">{d.users_count}</TableCell>
                            <TableCell className="text-center font-bold text-slate-700">{d.active_cases}</TableCell>
                            <TableCell className="text-xs text-muted-foreground font-mono bg-slate-50 px-2 py-1 rounded inline-block my-2">
                              {d.applicable_tier}
                            </TableCell>
                            <TableCell className="text-right font-bold text-emerald-600">
                              ${d.total_cost.toLocaleString('es-CO')} COP
                            </TableCell>
                          </TableRow>
                        ))}
                        {simulatorData.length === 0 && (
                          <TableRow>
                            <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                              No hay empresas registradas para simular facturación.
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* Modal Crear Empresa */}
      <Dialog open={isCompanyModalOpen} onOpenChange={setIsCompanyModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nueva Empresa</DialogTitle>
            <DialogDescription>Crea un nuevo inquilino para el modelo SaaS.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>Nombre de la Empresa</Label>
              <Input value={newCompany.nombre} onChange={e => setNewCompany({...newCompany, nombre: e.target.value})} placeholder="Ej. Emdecob Jurídica SAS" />
            </div>
            <div>
              <Label>NIT (Identificación Tributaria)</Label>
              <Input value={newCompany.nit} onChange={e => setNewCompany({...newCompany, nit: e.target.value})} placeholder="Ej. 900.123.456-7" />
            </div>
            <div>
              <Label>Límite de Usuarios Permitidos</Label>
              <Input type="number" value={newCompany.limite_usuarios} onChange={e => setNewCompany({...newCompany, limite_usuarios: parseInt(e.target.value) || 0})} />
            </div>
            <div>
              <Label>Logo de la Empresa (Opcional)</Label>
              <Input type="file" accept="image/*" onChange={handleNewLogoUpload} />
              {newCompany.logo_base64 && <img src={newCompany.logo_base64} alt="Logo preview" className="mt-2 h-12 object-contain" />}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCompanyModalOpen(false)}>Cancelar</Button>
            <Button onClick={handleCreateCompany} disabled={!newCompany.nombre} className="bg-blue-600 hover:bg-blue-500">Crear Empresa</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal Editar Empresa */}
      <Dialog open={isEditCompanyModalOpen} onOpenChange={setIsEditCompanyModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Editar Empresa</DialogTitle>
            <DialogDescription>Modifica los datos de la empresa inquilina.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>Nombre de la Empresa</Label>
              <Input 
                value={editCompanyForm.nombre} 
                onChange={e => setEditCompanyForm({...editCompanyForm, nombre: e.target.value})} 
              />
            </div>
            <div>
              <Label>NIT</Label>
              <Input 
                value={editCompanyForm.nit} 
                onChange={e => setEditCompanyForm({...editCompanyForm, nit: e.target.value})} 
              />
            </div>
            <div>
              <Label>Límite de Usuarios</Label>
              <Input 
                type="number"
                value={editCompanyForm.limite_usuarios} 
                onChange={e => setEditCompanyForm({...editCompanyForm, limite_usuarios: parseInt(e.target.value) || 0})} 
              />
            </div>
            <div>
              <Label>Logo de la Empresa</Label>
              <Input type="file" accept="image/*" onChange={handleEditLogoUpload} />
              {editCompanyForm.logo_base64 && <img src={editCompanyForm.logo_base64} alt="Logo preview" className="mt-2 h-12 object-contain" />}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setIsEditCompanyModalOpen(false);
              setEditingCompany(null);
            }}>
              Cancelar
            </Button>
            <Button 
              onClick={() => handleUpdateCompanyInfo(editingCompany.id, editCompanyForm)} 
              disabled={!editCompanyForm.nombre}
              className="bg-blue-600 hover:bg-blue-500"
            >
              Guardar Cambios
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal Crear Usuario */}
      <Dialog open={isUserModalOpen} onOpenChange={setIsUserModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nuevo Usuario</DialogTitle>
            <DialogDescription>Crea un usuario y asígnalo a una empresa con sus respectivos roles.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2 max-h-[70vh] overflow-y-auto pr-2">
            <div>
              <Label>Username (Login)</Label>
              <Input value={newUser.username} onChange={e => setNewUser({...newUser, username: e.target.value})} placeholder="Ej. karina.florez" />
            </div>
            <div>
              <Label>Contraseña</Label>
              <Input type="password" value={newUser.password} onChange={e => setNewUser({...newUser, password: e.target.value})} placeholder="Mínimo 6 caracteres" />
            </div>
            <div>
              <Label>Nombre Completo</Label>
              <Input value={newUser.nombre} onChange={e => setNewUser({...newUser, nombre: e.target.value})} placeholder="Ej. Ana Karina Florez" />
            </div>
            <div>
              <Label>Correo Electrónico</Label>
              <Input type="email" value={newUser.email} onChange={e => setNewUser({...newUser, email: e.target.value})} placeholder="Ej. karina@emdecob.com" />
            </div>
            <div>
              <Label>Empresa</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 text-slate-800"
                value={newUser.company_id}
                onChange={e => {
                  const val = e.target.value;
                  const isGlobal = val === 'global' || val === '';
                  setNewUser({
                    ...newUser,
                    company_id: val,
                    role: isGlobal ? 'SUPERADMIN' : 'USER',
                    cases_view_scope: isGlobal ? 'GLOBAL' : 'OWN'
                  });
                }}
              >
                <option value="" className="text-slate-400">Seleccionar Empresa...</option>
                <option value="global" className="font-semibold">Acceso Global (SuperAdmin)</option>
                {companies.map(c => (
                  <option key={c.id} value={c.id.toString()}>{c.nombre}</option>
                ))}
              </select>
            </div>
            
            {newUser.company_id && newUser.company_id !== 'global' && (
              <>
                <div>
                  <Label>Rol dentro de la empresa</Label>
                  <select
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring text-slate-800"
                    value={newUser.role}
                    onChange={e => {
                      const newRole = e.target.value;
                      let newScope = newUser.cases_view_scope;
                      if (newRole === 'USER') {
                        newScope = 'OWN';
                      } else if (newRole === 'COMPANY_ADMIN' && newScope === 'GLOBAL') {
                        newScope = 'COMPANY';
                      }
                      setNewUser({
                        ...newUser,
                        role: newRole,
                        cases_view_scope: newScope
                      });
                    }}
                  >
                    <option value="USER">USER (Estándar)</option>
                    <option value="COMPANY_ADMIN">COMPANY_ADMIN (Administrador de Empresa)</option>
                  </select>
                </div>
                <div>
                  <Label>Alcance de Visualización de Casos (Cases View Scope)</Label>
                  <select
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring text-slate-800"
                    value={newUser.cases_view_scope}
                    onChange={e => setNewUser({...newUser, cases_view_scope: e.target.value})}
                  >
                    <option value="OWN">OWN (Solo sus propios casos asignados)</option>
                    {newUser.role === 'COMPANY_ADMIN' && (
                      <option value="COMPANY">COMPANY (Todos los casos de la empresa)</option>
                    )}
                  </select>
                </div>
              </>
            )}
            {/* ClickUp Sync options */}
            <div className="flex items-center justify-between p-3.5 bg-slate-50/50 border border-slate-100 rounded-xl mt-2">
              <div className="space-y-0.5">
                <Label className="text-sm font-bold text-slate-700">Sincronizar con ClickUp</Label>
                <p className="text-[10px] text-muted-foreground leading-normal">Si está activo, este usuario solo podrá sincronizar con ClickUp y no creará elementos locales de cero.</p>
              </div>
              <input 
                type="checkbox" 
                checked={newUser.sync_with_clickup} 
                onChange={e => setNewUser({...newUser, sync_with_clickup: e.target.checked})}
                className="h-4.5 w-4.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
              />
            </div>
            <div>
              <Label>ClickUp API Token (Opcional)</Label>
              <Input 
                value={newUser.clickup_api_token} 
                onChange={e => setNewUser({...newUser, clickup_api_token: e.target.value})} 
                placeholder="Token ClickUp para este usuario..."
                type="password"
                className="mt-1"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsUserModalOpen(false)}>Cancelar</Button>
            <Button onClick={handleCreateUser} disabled={!newUser.username || !newUser.password || !newUser.company_id} className="bg-blue-600 hover:bg-blue-500">Crear Usuario</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal Editar Usuario */}
      <Dialog open={isEditUserModalOpen} onOpenChange={setIsEditUserModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Editar Usuario</DialogTitle>
            <DialogDescription>Modifica los datos, rol y alcance de este usuario.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2 max-h-[70vh] overflow-y-auto pr-2">
            <div>
              <Label>Nombre Completo</Label>
              <Input 
                value={editUserForm.nombre} 
                onChange={e => setEditUserForm({...editUserForm, nombre: e.target.value})} 
              />
            </div>
            <div>
              <Label>Correo Electrónico</Label>
              <Input 
                type="email" 
                value={editUserForm.email} 
                onChange={e => setEditUserForm({...editUserForm, email: e.target.value})} 
              />
            </div>
            <div>
              <Label>Nueva Contraseña (dejar vacío para no cambiar)</Label>
              <Input 
                type="password" 
                value={editUserForm.password} 
                onChange={e => setEditUserForm({...editUserForm, password: e.target.value})} 
                placeholder="Nueva contraseña..."
              />
            </div>
            <div>
              <Label>Empresa</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 text-slate-800"
                value={editUserForm.company_id}
                onChange={e => {
                  const val = e.target.value;
                  const isGlobal = val === 'global' || val === '';
                  setEditUserForm({
                    ...editUserForm, 
                    company_id: val,
                    role: isGlobal ? 'SUPERADMIN' : 'USER',
                    cases_view_scope: isGlobal ? 'GLOBAL' : 'OWN'
                  });
                }}
              >
                <option value="global" className="font-semibold">Acceso Global (SuperAdmin)</option>
                {companies.map(c => (
                  <option key={c.id} value={c.id.toString()}>{c.nombre}</option>
                ))}
              </select>
            </div>
            
            {editUserForm.company_id !== 'global' && (
              <>
                <div>
                  <Label>Rol dentro de la empresa</Label>
                  <select
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 text-slate-800"
                    value={editUserForm.role}
                    onChange={e => {
                      const newRole = e.target.value;
                      let newScope = editUserForm.cases_view_scope;
                      if (newRole === 'USER') {
                        newScope = 'OWN';
                      } else if (newRole === 'COMPANY_ADMIN' && newScope === 'GLOBAL') {
                        newScope = 'COMPANY';
                      }
                      setEditUserForm({
                        ...editUserForm,
                        role: newRole,
                        cases_view_scope: newScope
                      });
                    }}
                  >
                    <option value="USER">USER (Estándar)</option>
                    <option value="COMPANY_ADMIN">COMPANY_ADMIN (Administrador de Empresa)</option>
                  </select>
                </div>
                <div>
                  <Label>Alcance de Visualización de Casos (Cases View Scope)</Label>
                  <select
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 text-slate-800"
                    value={editUserForm.cases_view_scope}
                    onChange={e => setEditUserForm({...editUserForm, cases_view_scope: e.target.value})}
                  >
                    <option value="OWN">OWN (Solo sus propios casos asignados)</option>
                    {editUserForm.role === 'COMPANY_ADMIN' && (
                      <option value="COMPANY">COMPANY (Todos los casos de la empresa)</option>
                    )}
                  </select>
                </div>
              </>
            )}
            {/* ClickUp Sync options */}
            <div className="flex items-center justify-between p-3.5 bg-slate-50/50 border border-slate-100 rounded-xl mt-2">
              <div className="space-y-0.5">
                <Label className="text-sm font-bold text-slate-700">Sincronizar con ClickUp</Label>
                <p className="text-[10px] text-muted-foreground leading-normal">Si está activo, este usuario solo podrá sincronizar con ClickUp y no creará elementos locales de cero.</p>
              </div>
              <input 
                type="checkbox" 
                checked={editUserForm.sync_with_clickup} 
                onChange={e => setEditUserForm({...editUserForm, sync_with_clickup: e.target.checked})}
                className="h-4.5 w-4.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
              />
            </div>
            <div>
              <Label>ClickUp API Token (Opcional)</Label>
              <Input 
                value={editUserForm.clickup_api_token} 
                onChange={e => setEditUserForm({...editUserForm, clickup_api_token: e.target.value})} 
                placeholder="Dejar vacío o ingresar nuevo token..."
                type="password"
                className="mt-1"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setIsEditUserModalOpen(false);
              setEditingUser(null);
            }}>
              Cancelar
            </Button>
            <Button onClick={handleEditUserSubmit} disabled={!editUserForm.nombre} className="bg-blue-600 hover:bg-blue-500">
              Guardar Cambios
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal Suspender Empresa */}
      <Dialog open={suspendModalOpen} onOpenChange={setSuspendModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-destructive flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 animate-pulse" /> Suspender Empresa
            </DialogTitle>
            <DialogDescription>
              Esta acción bloqueará el acceso de todos los usuarios de esta empresa, pero no eliminará sus datos.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>Motivo de suspensión <span className="text-destructive">*</span></Label>
              <Input 
                value={suspendReason} 
                onChange={e => setSuspendReason(e.target.value)} 
                placeholder="Ej. Falta de pago" 
              />
            </div>
            <div>
              <Label>Observación interna</Label>
              <Textarea 
                value={suspendNotes} 
                onChange={e => setSuspendNotes(e.target.value)} 
                placeholder="Detalles adicionales para uso interno..."
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSuspendModalOpen(false)}>Cancelar</Button>
            <Button variant="destructive" onClick={handleSuspendCompany} disabled={!suspendReason}>Confirmar Suspensión</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
