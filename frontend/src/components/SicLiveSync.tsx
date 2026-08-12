import React, { useEffect, useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { RefreshCw, CheckCircle2, AlertCircle, ShieldCheck } from 'lucide-react';
import { apiFetch } from '@/services/api';

interface SicLiveSyncProps {
  caseId: number;
  radicado: string;
  cedula?: string;
  onSyncComplete: () => void;
}

export const SicLiveSync: React.FC<SicLiveSyncProps> = ({
  caseId,
  radicado,
  cedula = '',
  onSyncComplete
}) => {
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState<string>('');
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);

  // Parse radicado
  const cleanRad = (radicado || '').trim();
  const parts = cleanRad.split('-');
  const anio = parts.length > 1 ? parts[0] : '25';
  const numero = parts.length > 1 ? parts[1] : cleanRad;

  const handleTurnstileCallback = async (token: string) => {
    try {
      setStatus('loading');
      setMessage('Obteniendo actuaciones de la SIC...');

      const apiUrl = `https://apiexternotramites.sic.gov.co/consulta-externa/v1/radicados/anio/${anio}/numeros/${numero}${cedula ? `?tipoDocumento=CC&numeroDocumento=${cedula}` : ''}`;
      
      const res = await fetch(apiUrl, {
        method: 'GET',
        headers: {
          'Accept': 'application/json, text/plain, */*',
          'X-Turnstile-Token': token
        }
      });

      const data = await res.json();
      if (data.success && data.data && Array.isArray(data.data.content)) {
        const items = data.data.content;
        setMessage(`Guardando ${items.length} actuaciones en la base de datos...`);

        // Post back to our backend
        await apiFetch(`/api/cases/${caseId}/sync-sic-payload`, {
          method: 'POST',
          body: JSON.stringify({ items })
        });

        setStatus('success');
        setMessage(`¡Sincronización exitosa! ${items.length} actuaciones actualizadas.`);
        setTimeout(() => {
          onSyncComplete();
        }, 1200);
      } else {
        const err = data.errors?.[0] || data.message || 'No se obtuvieron registros de la SIC';
        setStatus('error');
        setMessage(err);
      }
    } catch (e: any) {
      console.error('Error sincronizando SIC:', e);
      setStatus('error');
      setMessage('Error conectando con la SIC. Intenta de nuevo.');
    }
  };

  useEffect(() => {
    // Definir callback global para Turnstile
    (window as any).onSicTurnstileSuccess = (token: string) => {
      handleTurnstileCallback(token);
    };

    // Cargar script de Turnstile si no existe
    if (!document.getElementById('cf-turnstile-script')) {
      const script = document.createElement('script');
      script.id = 'cf-turnstile-script';
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      script.async = true;
      script.defer = true;
      script.onload = () => {
        renderWidget();
      };
      document.body.appendChild(script);
    } else {
      renderWidget();
    }

    function renderWidget() {
      if ((window as any).turnstile && containerRef.current && !widgetIdRef.current) {
        try {
          const id = (window as any).turnstile.render(containerRef.current, {
            sitekey: '0x4AAAAAACGGiW1_wICMwND-',
            callback: 'onSicTurnstileSuccess',
            'error-callback': () => {
              setStatus('error');
              setMessage('Error en verificación de seguridad Turnstile.');
            }
          });
          widgetIdRef.current = id;
        } catch (e) {
          console.error('Error renderizando Turnstile:', e);
        }
      }
    }

    return () => {
      if (widgetIdRef.current && (window as any).turnstile) {
        try {
          (window as any).turnstile.remove(widgetIdRef.current);
          widgetIdRef.current = null;
        } catch (e) {}
      }
    };
  }, [caseId, radicado]);

  return (
    <div className="p-4 rounded-xl border bg-gradient-to-r from-blue-500/10 via-indigo-500/10 to-blue-500/10 border-blue-500/30 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
      <div className="flex items-start gap-3">
        <ShieldCheck className="h-6 w-6 text-blue-600 mt-0.5 shrink-0 animate-pulse" />
        <div>
          <h4 className="font-bold text-sm text-blue-950 dark:text-blue-200 flex items-center gap-2">
            Sincronización Oficial en Vivo SIC (Superintendencia de Industria y Comercio)
          </h4>
          <p className="text-xs text-muted-foreground mt-0.5">
            {status === 'idle' && 'Verifica la seguridad a continuación para consultar y actualizar el 100% de las actuaciones en tiempo real.'}
            {status === 'loading' && (message || 'Sincronizando actuaciones oficiales...')}
            {status === 'success' && (message || '¡Actuaciones actualizadas correctamente!')}
            {status === 'error' && (message || 'Error en la sincronización.')}
          </p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row items-center gap-3 shrink-0">
        {status === 'idle' && (
          <div ref={containerRef} id="cf-turnstile-container" className="my-1" />
        )}

        {status === 'loading' && (
          <div className="flex items-center gap-2 text-xs font-semibold text-blue-700 bg-blue-100 dark:bg-blue-900/40 px-3 py-1.5 rounded-lg">
            <RefreshCw className="h-4 w-4 animate-spin text-blue-600" />
            Sincronizando...
          </div>
        )}

        {status === 'success' && (
          <div className="flex items-center gap-2 text-xs font-semibold text-emerald-700 bg-emerald-100 dark:bg-emerald-900/40 px-3 py-1.5 rounded-lg">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            Actualizado
          </div>
        )}

        {status === 'error' && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setStatus('idle');
              setMessage('');
              if (widgetIdRef.current && (window as any).turnstile) {
                try {
                  (window as any).turnstile.reset(widgetIdRef.current);
                } catch (e) {}
              }
            }}
            className="gap-1.5 text-xs border-amber-300 text-amber-800 dark:text-amber-200 hover:bg-amber-500/20"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Reintentar
          </Button>
        )}
      </div>
    </div>
  );
};
