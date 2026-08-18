import { useEffect, useState } from "react";
import {
  Mail,
  Server,
  Save,
  Send,
  Loader2,
  CheckCircle2,
  XCircle,
  Eye,
  EyeOff,
  Bell,
  History,
  Lock,
} from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { useToast } from "@/hooks/use-toast";

import {
  getNotificationConfig,
  updateNotificationConfig,
  testNotificationEmail,
  getNotificationLogs,
  changePassword,
  type NotificationConfigResponse,
  type NotificationLogItem,
} from "@/services/api";

export default function ConfiguracionPage() {
  const { toast } = useToast();

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const [config, setConfig] = useState<NotificationConfigResponse | null>(null);
  const [logs, setLogs] = useState<NotificationLogItem[]>([]);

  // Security state
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [showOldPass, setShowOldPass] = useState(false);
  const [showNewPass, setShowNewPass] = useState(false);

  // Form state
  const [smtpHost, setSmtpHost] = useState("smtp.gmail.com");
  const [smtpPort, setSmtpPort] = useState<number>(587);
  const [smtpUser, setSmtpUser] = useState("");
  const [smtpPass, setSmtpPass] = useState("");
  const [smtpFrom, setSmtpFrom] = useState("");
  const [notificationEmails, setNotificationEmails] = useState("");
  const [isActive, setIsActive] = useState(false);
  const [testEmail, setTestEmail] = useState("");

  useEffect(() => {
    void loadConfig();
    void loadLogs();
  }, []);

  const loadConfig = async () => {
    try {
      const data = await getNotificationConfig();
      setConfig(data);

      setSmtpHost(data.smtp_host || "smtp.gmail.com");
      setSmtpPort(data.smtp_port || 587);
      setSmtpUser(data.smtp_user || "");
      setSmtpFrom(data.smtp_from || "");
      setNotificationEmails(data.notification_emails || "");
      setIsActive(Boolean(data.is_active));
    } catch (error: any) {
      toast({
        title: "Error cargando configuración",
        description: error?.message || "Error desconocido",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const loadLogs = async () => {
    try {
      const data = await getNotificationLogs(1, 10);
      setLogs(data.items || []);
    } catch (error) {
      console.error("Error cargando logs:", error);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await updateNotificationConfig({
        smtp_host: smtpHost,
        smtp_port: smtpPort,
        smtp_user: smtpUser,
        smtp_pass: smtpPass || undefined,
        smtp_from: smtpFrom,
        notification_emails: notificationEmails,
        is_active: isActive,
      });

      toast({
        title: "Configuración guardada",
        description: "Los cambios se han guardado correctamente",
      });

      setSmtpPass("");
      await loadConfig();
      await loadLogs();
    } catch (error: any) {
      toast({
        title: "Error guardando",
        description: error?.message || "Error desconocido",
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleChangePassword = async () => {
    if (!oldPassword || !newPassword || !confirmNewPassword) {
      toast({ title: "Campos requeridos", description: "Completa todos los campos de contraseña", variant: "destructive" });
      return;
    }
    if (newPassword !== confirmNewPassword) {
      toast({ title: "Error", description: "Las nuevas contraseñas no coinciden", variant: "destructive" });
      return;
    }

    setIsChangingPassword(true);
    try {
      await changePassword({ old_password: oldPassword, new_password: newPassword });
      toast({ title: "Éxito", description: "Contraseña actualizada correctamente" });
      setOldPassword("");
      setNewPassword("");
      setConfirmNewPassword("");
    } catch (error: any) {
      toast({ title: "Error", description: error?.message || "No se pudo cambiar la contraseña", variant: "destructive" });
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleTest = async () => {
    if (!testEmail.trim()) {
      toast({
        title: "Ingresa un correo",
        description: "Debes ingresar un correo para enviar la prueba",
        variant: "destructive",
      });
      return;
    }

    setIsTesting(true);
    try {
      await testNotificationEmail(testEmail.trim());
      toast({
        title: "Correo enviado",
        description: `Se envió un correo de prueba a ${testEmail.trim()}`,
      });
      await loadLogs();
    } catch (error: any) {
      toast({
        title: "Error enviando correo",
        description: error?.message || "Verifica la configuración SMTP",
        variant: "destructive",
      });
    } finally {
      setIsTesting(false);
    }
  };

  const formatDate = (dateString?: string | null) => {
    if (!dateString) return "—";
    const d = new Date(dateString);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleString("es-CO", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Configuración</h1>
        <p className="text-muted-foreground mt-2">
          Configura las notificaciones por correo electrónico
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Configuración SMTP */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5 text-primary" />
              Servidor SMTP
            </CardTitle>
            <CardDescription>
              Configuración del servidor de correo saliente
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="smtp_host">Host SMTP</Label>
                <Input
                  id="smtp_host"
                  value={smtpHost}
                  onChange={(e) => setSmtpHost(e.target.value)}
                  placeholder="smtp.gmail.com"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="smtp_port">Puerto</Label>
                <Input
                  id="smtp_port"
                  type="number"
                  value={smtpPort}
                  onChange={(e) => {
                    const n = Number(e.target.value);
                    setSmtpPort(Number.isFinite(n) ? n : 587);
                  }}
                  placeholder="587"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="smtp_user">Usuario (correo)</Label>
              <Input
                id="smtp_user"
                type="email"
                value={smtpUser}
                onChange={(e) => setSmtpUser(e.target.value)}
                placeholder="tu_correo@gmail.com"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="smtp_pass">
                Contraseña de aplicación
                {config?.has_password && (
                  <span className="text-xs text-muted-foreground ml-2">(ya configurada)</span>
                )}
              </Label>

              <div className="relative">
                <Input
                  id="smtp_pass"
                  type={showPassword ? "text" : "password"}
                  value={smtpPass}
                  onChange={(e) => setSmtpPass(e.target.value)}
                  placeholder={config?.has_password ? "••••••••" : "Contraseña de aplicación"}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="absolute right-0 top-0 h-full px-3"
                  onClick={() => setShowPassword((v) => !v)}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>

              <p className="text-xs text-muted-foreground">
                Para Gmail, usa una{" "}
                <a
                  href="https://support.google.com/accounts/answer/185833"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary underline"
                >
                  contraseña de aplicación
                </a>
                .
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="smtp_from">Correo remitente (opcional)</Label>
              <Input
                id="smtp_from"
                type="email"
                value={smtpFrom}
                onChange={(e) => setSmtpFrom(e.target.value)}
                placeholder="notificaciones@tuempresa.com"
              />
            </div>
          </CardContent>
        </Card>

        {/* Correos destino */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="h-5 w-5 text-primary" />
              Correos Destino
            </CardTitle>
            <CardDescription>
              Correos que recibirán las notificaciones de nuevas actuaciones
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="notification_emails">Correos (separados por coma)</Label>
              <Textarea
                id="notification_emails"
                value={notificationEmails}
                onChange={(e) => setNotificationEmails(e.target.value)}
                placeholder="correo1@empresa.com, correo2@empresa.com"
                rows={4}
              />
            </div>

            <div className="flex items-center justify-between p-4 rounded-lg bg-muted/30 border">
              <div className="space-y-1">
                <Label htmlFor="is_active" className="font-medium">
                  Activar notificaciones
                </Label>
                <p className="text-xs text-muted-foreground">
                  Enviar correos automáticos cuando haya nuevas actuaciones
                </p>
              </div>

              <Switch id="is_active" checked={isActive} onCheckedChange={setIsActive} />
            </div>

            <div className="pt-4 border-t space-y-3">
              <Label>Enviar correo de prueba</Label>
              <div className="flex gap-2">
                <Input
                  type="email"
                  value={testEmail}
                  onChange={(e) => setTestEmail(e.target.value)}
                  placeholder="correo@ejemplo.com"
                />
                <Button onClick={handleTest} disabled={isTesting} variant="outline">
                  {isTesting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Guardar */}
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={isSaving} size="lg">
          {isSaving ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Save className="h-4 w-4 mr-2" />
          )}
          Guardar Configuración
        </Button>
      </div>

      {/* Sección de Seguridad */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lock className="h-5 w-5 text-primary" />
            Seguridad
          </CardTitle>
          <CardDescription>Cambia tu contraseña de acceso</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 max-w-2xl">
          <div className="space-y-2">
            <Label htmlFor="old_pass">Contraseña Actual</Label>
            <div className="relative">
              <Input
                id="old_pass"
                type={showOldPass ? "text" : "password"}
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
              />
              <Button
                variant="ghost"
                size="sm"
                className="absolute right-0 top-0 h-full px-3"
                onClick={() => setShowOldPass(!showOldPass)}
              >
                {showOldPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
            </div>
          </div>
          
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="new_pass">Nueva Contraseña</Label>
              <div className="relative">
                <Input
                  id="new_pass"
                  type={showNewPass ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
                <Button
                  variant="ghost"
                  size="sm"
                  className="absolute right-0 top-0 h-full px-3"
                  onClick={() => setShowNewPass(!showNewPass)}
                >
                  {showNewPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm_new_pass">Confirmar Nueva Contraseña</Label>
              <Input
                id="confirm_new_pass"
                type={showNewPass ? "text" : "password"}
                value={confirmNewPassword}
                onChange={(e) => setConfirmNewPassword(e.target.value)}
              />
            </div>
          </div>
          
          <Button onClick={handleChangePassword} disabled={isChangingPassword}>
            {isChangingPassword && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Actualizar Contraseña
          </Button>
        </CardContent>
      </Card>

      {/* Historial */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5 text-primary" />
            Historial de Notificaciones
          </CardTitle>
          <CardDescription>Últimas notificaciones enviadas</CardDescription>
        </CardHeader>

        <CardContent>
          {logs.length === 0 ? (
            <div className="text-center py-8">
              <Bell className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No hay notificaciones enviadas</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Fecha</TableHead>
                  <TableHead>Destinatarios</TableHead>
                  <TableHead>Casos</TableHead>
                  <TableHead>Estado</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                {logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="text-sm">{formatDate(log.sent_at)}</TableCell>

                    <TableCell className="text-sm max-w-[200px] truncate">
                      {log.recipients || "—"}
                    </TableCell>

                    <TableCell>
                      <Badge variant="outline">{log.cases_count}</Badge>
                    </TableCell>

                    <TableCell>
                      {log.status === "sent" ? (
                        <div className="flex items-center gap-1 text-green-600">
                          <CheckCircle2 className="h-4 w-4" />
                          <span className="text-sm">Enviado</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1 text-destructive">
                          <XCircle className="h-4 w-4" />
                          <span className="text-sm">Error</span>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
