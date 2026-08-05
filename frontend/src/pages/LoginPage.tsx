import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/hooks/use-toast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { 
  Lock, 
  User,
  Eye, 
  EyeOff,
  Loader2,
  ArrowRight,
  Mail,
  Shield,
  Headphones,
  Building2,
  CheckCircle2,
  ArrowLeft
} from 'lucide-react';
import { registerCompany, forgotPassword } from '@/services/api';

/* Use a new filename to absolutely bypass any cache */
const LOGIN_BG = "/login-vfinal.png";

interface LoginPageProps {
  initialView?: 'login' | 'register' | 'forgot_password';
}

export default function LoginPage({ initialView = 'login' }: LoginPageProps) {
  const [view, setView] = useState<'login' | 'register' | 'forgot_password'>(initialView);

  useEffect(() => {
    setView(initialView);
  }, [initialView]);
  
  // Login State
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [rememberMe, setRememberMe] = useState(false);
  
  // Register State
  const [regCompany, setRegCompany] = useState('');
  const [regNit, setRegNit] = useState('');
  const [regAdmin, setRegAdmin] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirm, setRegConfirm] = useState('');
  
  // Forgot Password State
  const [forgotEmail, setForgotEmail] = useState('');
  
  const { login } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/consultar';

  const handleForgotPasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!forgotEmail) {
      setLoginError('Por favor ingrese su correo');
      return;
    }
    setLoginError(null);
    setIsSubmitting(true);
    try {
      const res = await forgotPassword(forgotEmail);
      toast({
        title: "Correo enviado",
        description: res.message,
      });
      setView('login');
    } catch (e: any) {
      setLoginError(e.message || 'Error al solicitar recuperación');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    if (regPassword !== regConfirm) {
      setLoginError('Las contraseñas no coinciden');
      return;
    }
    setIsSubmitting(true);
    try {
      const res = await registerCompany({
        company_name: regCompany,
        company_nit: regNit,
        admin_name: regAdmin,
        email: regEmail,
        password: regPassword,
        confirm_password: regConfirm
      });
      toast({
        title: "Cuenta creada",
        description: res.message,
      });
      setView('login');
      setUsername(regEmail);
    } catch (e: any) {
      setLoginError(e.message || 'Error al registrar empresa');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) {
      setLoginError('Por favor ingrese usuario y contraseña');
      return;
    }
    setLoginError(null);
    setIsSubmitting(true);
    const result = await login({ username, password });
    setIsSubmitting(false);
    if (result.success) {
      navigate(from, { replace: true });
    } else {
      setLoginError(result.error || 'Usuario o contraseña incorrectos');
    }
  };

  return (
    <div className="min-h-screen w-full relative flex overflow-hidden">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Outfit:wght@300;400;500;600;700&display=swap');
        
        .font-serif-juricob { font-family: 'Cinzel', serif; }
        .font-sans-juricob { font-family: 'Outfit', sans-serif; }

        .full-bg {
          position: absolute;
          inset: 0;
          background-image: url(${LOGIN_BG});
          background-size: 100% auto; /* Ajuste para reducir el zoom */
          background-position: center;
          background-repeat: no-repeat;
          background-color: #021C33; /* Fondo oscuro por si la imagen no cubre todo */
          z-index: 1;
        }

        .overlay-content {
          position: relative;
          z-index: 10;
          width: 100%;
          height: 100vh;
          display: flex;
        }

        .branding-area-spacer {
          flex: 0 0 50%;
        }

        .form-area {
          flex: 1;
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
          padding: 2rem;
          padding-left: 12%;
        }

        @media (max-width: 1024px) {
          .branding-area-spacer { display: none; }
          .form-area { flex: 1; padding-left: 0; }
          .full-bg { background-position: 80% center; }
        }

        .premium-login-card {
          width: 100%;
          max-width: 520px;
          background: white;
          border-radius: 3rem;
          box-shadow: 0 40px 100px -20px rgba(0,0,0,0.15);
          padding: 4rem 3.5rem;
          border: 1px solid #f1f5f9;
        }

        .btn-target-grad {
          background: linear-gradient(90deg, #021C33 0%, #064e3b 60%, #10b981 100%);
        }
      `}</style>

      {/* The new clean background image */}
      <div className="full-bg" />

      {/* Content Overlay */}
      <div className="overlay-content">
        <div className="branding-area-spacer" />

        <div className="form-area">
          <div className="premium-login-card animate-in fade-in zoom-in duration-700">
            <div className="text-center mb-12 relative">
              {view !== 'login' && (
                <Button variant="ghost" size="icon" onClick={() => setView('login')} className="absolute left-0 top-0 text-[#021C33]">
                  <ArrowLeft className="h-6 w-6" />
                </Button>
              )}
              <h1 className="text-3xl font-normal text-[#021C33] font-serif-juricob uppercase tracking-[0.2em] mb-8">
                {view === 'login' ? 'Acceso seguro' : view === 'register' ? 'Crear cuenta' : 'Recuperación'}
              </h1>
              <div className="flex items-center justify-center gap-6">
                <div className="h-[1.5px] flex-1 bg-slate-100"></div>
                <div className="w-20 h-20 rounded-full border border-emerald-400 flex items-center justify-center bg-white shadow-sm">
                  {view === 'register' ? <Building2 className="w-8 h-8 text-[#021C33]" /> : <Lock className="w-8 h-8 text-[#021C33]" />}
                </div>
                <div className="h-[1.5px] flex-1 bg-slate-100"></div>
              </div>
            </div>

            {view === 'login' && (
              <form onSubmit={handleSubmit} className="space-y-8">
                <div className="space-y-3">
                  <Label htmlFor="u" className="text-sm font-bold text-slate-700 ml-1">Correo electrónico o usuario</Label>
                  <div className="relative group">
                    <User className="absolute left-4 top-1/2 -translate-y-1/2 h-6 w-6 text-slate-400 group-focus-within:text-emerald-600 transition-colors" />
                    <Input id="u" type="text" placeholder="ejemplo@correo.com o usuario" value={username} onChange={(e) => setUsername(e.target.value)} className="pl-14 h-14 bg-white border-2 border-slate-200 text-slate-900 font-semibold placeholder:text-slate-400 focus:border-emerald-500 focus:bg-white focus:text-slate-900 rounded-2xl text-base font-sans-juricob shadow-sm" />
                  </div>
                </div>

                <div className="space-y-3">
                  <Label htmlFor="p" className="text-sm font-bold text-slate-700 ml-1">Contraseña</Label>
                  <div className="relative group">
                    <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-6 w-6 text-slate-400 group-focus-within:text-emerald-600 transition-colors" />
                    <Input id="p" type={showPassword ? 'text' : 'password'} placeholder="••••••••••••" value={password} onChange={(e) => setPassword(e.target.value)} className="pl-14 pr-14 h-14 bg-white border-2 border-slate-200 text-slate-900 font-semibold placeholder:text-slate-400 focus:border-emerald-500 focus:bg-white focus:text-slate-900 rounded-2xl text-base font-sans-juricob shadow-sm" />
                    <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                      {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-between px-1">
                  <div className="flex items-center space-x-2 cursor-pointer group">
                    <input type="checkbox" id="rem" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} className="w-4 h-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-600 cursor-pointer" />
                    <label htmlFor="rem" className="text-xs text-slate-500 font-medium cursor-pointer group-hover:text-emerald-600 transition-colors">Recordarme</label>
                  </div>
                  <button type="button" onClick={() => { setView('forgot_password'); setLoginError(null); }} className="text-xs font-bold text-emerald-700 hover:text-emerald-500 transition-colors">¿Olvidaste tu contraseña?</button>
                </div>

                {loginError && <p className="text-red-500 text-[11px] text-center font-bold bg-red-50 py-2 rounded-lg">{loginError}</p>}

                <Button type="submit" disabled={isSubmitting} className="btn-target-grad w-full h-16 text-white rounded-2xl font-normal text-xl flex items-center justify-center gap-4 shadow-2xl shadow-emerald-900/10 hover:opacity-95 active:scale-[0.98] transition-all font-serif-juricob uppercase tracking-widest">
                  {isSubmitting ? <Loader2 className="h-6 w-6 animate-spin" /> : <><span>Iniciar sesión</span><ArrowRight className="h-6 w-6" /></>}
                </Button>

                <div className="relative py-4">
                  <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-slate-100"></div></div>
                  <div className="relative flex justify-center text-xs"><span className="bg-white px-8 text-slate-400 font-bold uppercase tracking-widest">¿No tienes una cuenta?</span></div>
                </div>

                <Button type="button" onClick={() => { setView('register'); setLoginError(null); }} variant="outline" className="w-full h-14 border-2 border-[#021C33] bg-white hover:bg-slate-100 text-[#021C33] font-bold rounded-2xl text-base flex items-center justify-center gap-2 transition-all shadow-sm active:scale-[0.98] cursor-pointer">Crear cuenta</Button>
              </form>
            )}

            {view === 'forgot_password' && (
              <form onSubmit={handleForgotPasswordSubmit} className="space-y-8">
                <p className="text-center text-sm text-slate-500">Ingresa tu correo o usuario y te enviaremos instrucciones para recuperar tu acceso.</p>
                <div className="space-y-3">
                  <Label htmlFor="fe" className="text-sm font-bold text-slate-700 ml-1">Correo electrónico o usuario</Label>
                  <div className="relative group">
                    <Mail className="absolute left-4 top-1/2 -translate-y-1/2 h-6 w-6 text-slate-400 group-focus-within:text-emerald-500 transition-colors" />
                    <Input id="fe" type="text" placeholder="ejemplo@correo.com o usuario" value={forgotEmail} onChange={(e) => setForgotEmail(e.target.value)} required className="pl-14 h-14 bg-white border-2 border-slate-200 text-slate-900 font-semibold placeholder:text-slate-400 focus:border-emerald-500 focus:bg-white focus:text-slate-900 rounded-2xl text-base font-sans-juricob shadow-sm" />
                  </div>
                </div>

                {loginError && <p className="text-red-500 text-[11px] text-center font-bold bg-red-50 py-2 rounded-lg">{loginError}</p>}

                <Button type="submit" disabled={isSubmitting} className="btn-target-grad w-full h-16 text-white rounded-2xl font-normal text-xl flex items-center justify-center gap-4 shadow-2xl shadow-emerald-900/10 hover:opacity-95 active:scale-[0.98] transition-all font-serif-juricob uppercase tracking-widest">
                  {isSubmitting ? <Loader2 className="h-6 w-6 animate-spin" /> : <><span>Enviar Enlace</span><ArrowRight className="h-6 w-6" /></>}
                </Button>
              </form>
            )}

            {view === 'register' && (
              <form onSubmit={handleRegisterSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-xs font-bold text-slate-700 ml-1">Empresa</Label>
                    <Input placeholder="Nombre Empresa" required value={regCompany} onChange={(e) => setRegCompany(e.target.value)} className="h-12 bg-white border-2 border-slate-200 text-slate-900 font-semibold focus:border-emerald-500 focus:bg-white rounded-xl" />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs font-bold text-slate-700 ml-1">NIT (Opcional)</Label>
                    <Input placeholder="123456" value={regNit} onChange={(e) => setRegNit(e.target.value)} className="h-12 bg-white border-2 border-slate-200 text-slate-900 font-semibold focus:border-emerald-500 focus:bg-white rounded-xl" />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label className="text-xs font-bold text-slate-700 ml-1">Administrador</Label>
                  <Input placeholder="Nombre completo" required value={regAdmin} onChange={(e) => setRegAdmin(e.target.value)} className="h-12 bg-white border-2 border-slate-200 text-slate-900 font-semibold focus:border-emerald-500 focus:bg-white rounded-xl" />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs font-bold text-slate-700 ml-1">Correo electrónico o usuario</Label>
                  <Input type="text" placeholder="ejemplo@correo.com o usuario" required value={regEmail} onChange={(e) => setRegEmail(e.target.value)} className="h-12 bg-white border-2 border-slate-200 text-slate-900 font-semibold focus:border-emerald-500 focus:bg-white rounded-xl" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-xs font-bold text-slate-700 ml-1">Contraseña</Label>
                    <Input type="password" required value={regPassword} onChange={(e) => setRegPassword(e.target.value)} className="h-12 bg-white border-2 border-slate-200 text-slate-900 font-semibold focus:border-emerald-500 focus:bg-white rounded-xl" />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs font-bold text-slate-700 ml-1">Confirmar</Label>
                    <Input type="password" required value={regConfirm} onChange={(e) => setRegConfirm(e.target.value)} className="h-12 bg-white border-2 border-slate-200 text-slate-900 font-semibold focus:border-emerald-500 focus:bg-white rounded-xl" />
                  </div>
                </div>

                {loginError && <p className="text-red-500 text-[11px] text-center font-bold bg-red-50 py-2 rounded-lg">{loginError}</p>}

                <Button type="submit" disabled={isSubmitting} className="btn-target-grad w-full h-14 mt-4 text-white rounded-2xl font-normal text-lg flex items-center justify-center gap-4 shadow-xl hover:opacity-95 active:scale-[0.98] transition-all uppercase tracking-widest">
                  {isSubmitting ? <Loader2 className="h-6 w-6 animate-spin" /> : 'Registrar Empresa'}
                </Button>
              </form>
            )}
          </div>

          {/* Footer Info - Centered with the card and larger */}
          <div className="flex items-center gap-12 mt-16 text-slate-400 animate-in fade-in slide-in-from-bottom duration-1000">
             <div className="flex items-center gap-4 hover:text-[#021C33] transition-colors cursor-default">
                <Shield className="w-8 h-8 text-[#021C33]" />
                <span className="uppercase tracking-[0.2em] text-[12px] font-bold">Plataforma Segura</span>
             </div>
             <div className="w-[1.5px] h-10 bg-slate-200" />
             <div className="flex items-center gap-4 hover:text-[#021C33] transition-colors cursor-default">
                <Headphones className="w-8 h-8 text-[#021C33]" />
                <div className="flex flex-col text-[12px] leading-tight font-bold">
                   <span className="uppercase tracking-[0.1em]">Soporte Especializado</span>
                   <span className="text-slate-400 font-normal text-[11px]">Asistencia profesional 24/7</span>
                </div>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
}
