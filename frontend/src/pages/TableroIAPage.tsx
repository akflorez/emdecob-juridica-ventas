import { useState, useEffect } from 'react';
import { 
  Sparkles, 
  Bot, 
  BrainCircuit, 
  AlertTriangle, 
  Clock, 
  FileText, 
  ShieldAlert, 
  ShieldCheck, 
  Search, 
  Send, 
  TrendingUp, 
  Zap, 
  CheckCircle2, 
  ChevronRight, 
  HelpCircle, 
  Scale, 
  ArrowUpRight,
  Filter,
  RefreshCw,
  Info
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { apiFetch } from '@/services/api';

interface AIProcessItem {
  id: number;
  radicado: string;
  demandante: string;
  demandado: string;
  juzgado: string;
  dias_sin_movimiento: number;
  nivel_riesgo: 'Alto' | 'Medio' | 'Bajo';
  termino_dias_restantes: number;
  resumen_ia: string;
  recomendacion_ia: string;
  tipo_sentencia?: 'Favorables' | 'Desfavorables' | 'En Trámite';
}

const SAMPLE_AI_DATA: AIProcessItem[] = [
  {
    id: 1,
    radicado: "11001400300120230048500",
    demandante: "FONDO NACIONAL DEL AHORRO",
    demandado: "CARLOS ALBERTO GÓMEZ",
    juzgado: "001 JUZGADO DE EJECUCIÓN CIVIL MUNICIPAL DE BOGOTÁ",
    dias_sin_movimiento: 195,
    nivel_riesgo: "Alto",
    termino_dias_restantes: 2,
    resumen_ia: "Auto de remate notificado por estado. La parte demandada presentó objeción al avalúo que requiere traslado inmediato.",
    recomendacion_ia: "Descorrer traslado de la objeción al avalúo antes del vencimiento del término de 3 días.",
    tipo_sentencia: "Desfavorables"
  },
  {
    id: 2,
    radicado: "05001310300220220031200",
    demandante: "BANCO AGRARIO DE COLOMBIA",
    demandado: "MARÍA ELENA GUTIÉRREZ",
    juzgado: "002 JUZGADO CIVIL DEL CIRCUITO DE MEDELLÍN",
    dias_sin_movimiento: 210,
    nivel_riesgo: "Alto",
    termino_dias_restantes: 4,
    resumen_ia: "Proceso paralizado en la etapa de medidas cautelares sin solicitud de impulso de embargo sobre inmueble identificado.",
    recomendacion_ia: "Radicar de manera urgente memorial de impulso procesal y solicitud de medidas de embargo adicionales.",
    tipo_sentencia: "En Trámite"
  },
  {
    id: 3,
    radicado: "76001400300520240011800",
    demandante: "CREDIVALORES S.A.",
    demandado: "JORGE ENRIQUE MARTÍNEZ",
    juzgado: "005 JUZGADO CIVIL MUNICIPAL DE CALI",
    dias_sin_movimiento: 45,
    nivel_riesgo: "Medio",
    termino_dias_restantes: 5,
    resumen_ia: "Orden de pago emitida favorablemente. Pendiente notificación a la parte ejecutada mediante aviso o conducta concluyente.",
    recomendacion_ia: "Verificar el estado de entrega del citatorio e iniciar trámites para la notificación por aviso.",
    tipo_sentencia: "Favorables"
  },
  {
    id: 4,
    radicado: "08001400300820230092100",
    demandante: "EMPRESA DE ENERGÍA DE PEREIRA",
    demandado: "CONSTRUCTORA ESTRUCTURAS S.A.S.",
    juzgado: "008 JUZGADO CIVIL MUNICIPAL DE BARRANQUILLA",
    dias_sin_movimiento: 240,
    nivel_riesgo: "Alto",
    termino_dias_restantes: 1,
    resumen_ia: "Sentencia de primera instancia con recurso de apelación concedido en efecto devolutivo.",
    recomendacion_ia: "Presentar sustentación del recurso de apelación dentro del término legal urgente.",
    tipo_sentencia: "Desfavorables"
  },
  {
    id: 5,
    radicado: "68001400300320240054200",
    demandante: "COOPEMPLEADOS BUCARAMANGA",
    demandado: "ANA BEATRIZ SILVA",
    juzgado: "003 JUZGADO CIVIL MUNICIPAL DE BUCARAMANGA",
    dias_sin_movimiento: 15,
    nivel_riesgo: "Bajo",
    termino_dias_restantes: 12,
    resumen_ia: "Medida cautelar de embargo de salarios aprobada y oficiada a la entidad pagadora.",
    recomendacion_ia: "Realizar seguimiento al ingreso de retenciones y títulos judiciales emitidos por el juzgado.",
    tipo_sentencia: "Favorables"
  }
];

export default function TableroIAPage() {
  const { toast } = useToast();
  const [searchQuery, setSearchQuery] = useState('');
  const [activePrompt, setActivePrompt] = useState<string | null>(null);
  const [isAiAnalyzing, setIsAiAnalyzing] = useState(false);
  const [filteredData, setFilteredData] = useState<AIProcessItem[]>(SAMPLE_AI_DATA);
  const [aiAnalysisSummary, setAiAnalysisSummary] = useState<string | null>(
    "El asistente de IA ha identificado 3 procesos de riesgo alto que requieren atención prioritaria esta semana por vencimiento de términos y falta de movimiento."
  );

  const QUICK_PROMPTS = [
    {
      icon: Clock,
      label: "¿Cuáles procesos llevan más de seis meses sin movimiento?",
      prompt: "procesos_sin_movimiento"
    },
    {
      icon: ShieldAlert,
      label: "Muéstrame las sentencias desfavorables del último trimestre",
      prompt: "sentencias_desfavorables"
    },
    {
      icon: AlertTriangle,
      label: "¿Qué procesos requieren atención esta semana?",
      prompt: "atencion_urgente"
    },
    {
      icon: Zap,
      label: "Identificar términos próximos a vencer (Menos de 5 días)",
      prompt: "terminos_vencer"
    }
  ];

  const handleQuerySelect = (promptKey: string, label: string) => {
    setActivePrompt(label);
    setIsAiAnalyzing(true);

    setTimeout(() => {
      setIsAiAnalyzing(false);
      if (promptKey === "procesos_sin_movimiento") {
        const res = SAMPLE_AI_DATA.filter(item => item.dias_sin_movimiento >= 180);
        setFilteredData(res);
        setAiAnalysisSummary(
          `🔍 **Análisis IA**: Se encontraron ${res.length} procesos congelados con más de 180 días sin actuación judicial. Se sugiere radicar impulso procesal para evitar desistimiento tácito.`
        );
      } else if (promptKey === "sentencias_desfavorables") {
        const res = SAMPLE_AI_DATA.filter(item => item.tipo_sentencia === "Desfavorables");
        setFilteredData(res);
        setAiAnalysisSummary(
          `⚖️ **Análisis IA**: Se hallaron ${res.length} procesos con decisiones desfavorables en el último trimestre. Requieren revisión de recursos de apelación y excepciones.`
        );
      } else if (promptKey === "atencion_urgente") {
        const res = SAMPLE_AI_DATA.filter(item => item.nivel_riesgo === "Alto" || item.termino_dias_restantes <= 3);
        setFilteredData(res);
        setAiAnalysisSummary(
          `🚨 **Análisis IA**: Se detectaron ${res.length} procesos en estado URGENTE con términos a vencer en menos de 72 horas.`
        );
      } else if (promptKey === "terminos_vencer") {
        const res = SAMPLE_AI_DATA.filter(item => item.termino_dias_restantes <= 5);
        setFilteredData(res);
        setAiAnalysisSummary(
          `⏳ **Análisis IA**: ${res.length} términos legales vencen en los próximos 5 días hábiles.`
        );
      }
      
      toast({
        title: "Análisis IA Completado",
        description: `Se han filtrado y analizado los procesos correctamente.`,
      });
    }, 600);
  };

  const handleCustomSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    
    setActivePrompt(searchQuery);
    setIsAiAnalyzing(true);

    setTimeout(() => {
      setIsAiAnalyzing(false);
      const queryLower = searchQuery.toLowerCase();
      const res = SAMPLE_AI_DATA.filter(item => 
        item.radicado.includes(queryLower) ||
        item.demandante.toLowerCase().includes(queryLower) ||
        item.demandado.toLowerCase().includes(queryLower) ||
        item.juzgado.toLowerCase().includes(queryLower) ||
        item.resumen_ia.toLowerCase().includes(queryLower)
      );
      
      setFilteredData(res.length > 0 ? res : SAMPLE_AI_DATA);
      setAiAnalysisSummary(
        `🤖 **Respuesta Asistente IA**: Se analizaron los expedientes para "${searchQuery}". Mostrando ${res.length > 0 ? res.length : SAMPLE_AI_DATA.length} resultados coincidentes con recomendaciones automáticas.`
      );
    }, 700);
  };

  const handleResetFilters = () => {
    setActivePrompt(null);
    setSearchQuery('');
    setFilteredData(SAMPLE_AI_DATA);
    setAiAnalysisSummary(
      "El asistente de IA ha identificado 3 procesos de riesgo alto que requieren atención prioritaria esta semana por vencimiento de términos y falta de movimiento."
    );
  };

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">
      
      {/* Banner Principal de Inteligencia Artificial */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-slate-900 via-emerald-950 to-slate-900 border border-emerald-500/30 p-8 shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl -z-0 pointer-events-none" />
        
        <div className="relative z-10 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
          <div className="space-y-3 max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-500/20 border border-emerald-400/30 text-emerald-300 text-xs font-bold uppercase tracking-widest">
              <Sparkles className="w-4 h-4 text-emerald-400 animate-pulse" />
              <span>Inteligencia Artificial Jurídica v2.5</span>
            </div>
            
            <h1 className="text-3xl md:text-4xl font-extrabold text-white font-serif-juricob tracking-tight">
              Tablero de IA & Analítica Predictiva Judicial
            </h1>
            
            <p className="text-slate-300 text-sm md:text-base leading-relaxed">
              Monitoreo inteligente, resumen automático de actuaciones, clasificación de riesgo y alertas automáticas de vencimiento para tomar decisiones estratégicas en tiempo real.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 w-full lg:w-auto">
            <Button onClick={handleResetFilters} variant="outline" className="border-emerald-500/40 text-emerald-300 hover:bg-emerald-950/50 bg-slate-900/80 rounded-xl flex items-center justify-center gap-2">
              <RefreshCw className="w-4 h-4" />
              <span>Restablecer Filtros</span>
            </Button>
          </div>
        </div>
      </div>

      {/* KPI Cards (Métricas Clave de IA) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <Card className="border-emerald-500/20 bg-card hover:border-emerald-500/50 transition-all shadow-md">
          <CardContent className="p-6 flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Términos a Vencer</p>
              <h3 className="text-3xl font-extrabold text-amber-500 mt-1">
                {SAMPLE_AI_DATA.filter(i => i.termino_dias_restantes <= 5).length}
              </h3>
              <p className="text-xs text-amber-600 dark:text-amber-400 mt-1 font-medium">⚠️ Próximos 5 días hábiles</p>
            </div>
            <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-500">
              <Clock className="w-6 h-6" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-emerald-500/20 bg-card hover:border-emerald-500/50 transition-all shadow-md">
          <CardContent className="p-6 flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Riesgo Alto Procesal</p>
              <h3 className="text-3xl font-extrabold text-red-500 mt-1">
                {SAMPLE_AI_DATA.filter(i => i.nivel_riesgo === 'Alto').length}
              </h3>
              <p className="text-xs text-red-500 mt-1 font-medium">🚨 Requieren impulso prioritario</p>
            </div>
            <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-500">
              <ShieldAlert className="w-6 h-6" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-emerald-500/20 bg-card hover:border-emerald-500/50 transition-all shadow-md">
          <CardContent className="p-6 flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Inactivos &gt; 6 Meses</p>
              <h3 className="text-3xl font-extrabold text-indigo-500 mt-1">
                {SAMPLE_AI_DATA.filter(i => i.dias_sin_movimiento >= 180).length}
              </h3>
              <p className="text-xs text-indigo-500 mt-1 font-medium">❄️ Sin movimiento en Rama</p>
            </div>
            <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-500">
              <BrainCircuit className="w-6 h-6" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-emerald-500/20 bg-card hover:border-emerald-500/50 transition-all shadow-md">
          <CardContent className="p-6 flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Resúmenes Generados</p>
              <h3 className="text-3xl font-extrabold text-emerald-500 mt-1">100%</h3>
              <p className="text-xs text-emerald-500 mt-1 font-medium">✨ Síntesis automática por IA</p>
            </div>
            <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-500">
              <Sparkles className="w-6 h-6" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* SECCIÓN DEL ASISTENTE VIRTUAL IA */}
      <Card className="border-emerald-500/30 bg-card shadow-xl overflow-hidden">
        <CardHeader className="bg-slate-900/90 text-white p-6 border-b border-emerald-500/20">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-400/40 flex items-center justify-center text-emerald-400">
              <Bot className="w-6 h-6" />
            </div>
            <div>
              <CardTitle className="text-xl font-bold flex items-center gap-2">
                <span>Asistente Jurídico Virtual con IA</span>
                <Badge variant="outline" className="border-emerald-400 text-emerald-400 text-[10px]">IA Conectada</Badge>
              </CardTitle>
              <CardDescription className="text-slate-300 text-xs mt-0.5">
                Haz preguntas en lenguaje natural o selecciona una de las consultas más frecuentes.
              </CardDescription>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-6 space-y-6">
          
          {/* Campo de Consulta en Lenguaje Natural */}
          <form onSubmit={handleCustomSearch} className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Escribe tu consulta (Ej: ¿Cuáles procesos tienen riesgo alto o vencimiento esta semana?)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-12 h-13 text-base rounded-2xl border-emerald-500/30 focus:border-emerald-500 bg-background"
              />
            </div>
            <Button type="submit" disabled={isAiAnalyzing} className="h-13 px-6 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-2xl flex items-center gap-2 shadow-lg">
              {isAiAnalyzing ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
              <span className="hidden sm:inline">Consultar IA</span>
            </Button>
          </form>

          {/* Chips de Consultas Rápidas (Directamente de la propuesta) */}
          <div className="space-y-2">
            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-emerald-500" />
              <span>Consultas Recomendadas por la IA:</span>
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {QUICK_PROMPTS.map((qp, idx) => {
                const IconComp = qp.icon;
                const isSelected = activePrompt === qp.label;
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleQuerySelect(qp.prompt, qp.label)}
                    className={`p-3.5 rounded-2xl border text-left flex items-center justify-between gap-3 transition-all ${
                      isSelected 
                        ? 'bg-emerald-500/15 border-emerald-500 text-emerald-400 font-bold shadow-md' 
                        : 'bg-muted/40 border-border/60 hover:bg-emerald-500/10 hover:border-emerald-500/40 text-foreground'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-emerald-500/20 text-emerald-500 flex items-center justify-center flex-shrink-0">
                        <IconComp className="w-4 h-4" />
                      </div>
                      <span className="text-xs font-medium">{qp.label}</span>
                    </div>
                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                  </button>
                );
              })}
            </div>
          </div>

          {/* Resumen Ejecutivo del Asistente */}
          {aiAnalysisSummary && (
            <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-900 dark:text-emerald-200 text-sm flex items-start gap-3 animate-in fade-in duration-300">
              <Info className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
              <div className="flex-1 leading-relaxed">
                <div dangerouslySetInnerHTML={{ __html: aiAnalysisSummary.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} />
              </div>
            </div>
          )}

        </CardContent>
      </Card>

      {/* TABLA Y CARDS DE RESULTADOS ANALIZADOS POR IA */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold font-serif-juricob text-foreground flex items-center gap-2">
            <Scale className="w-6 h-6 text-emerald-500" />
            <span>Procesos Analizados con IA ({filteredData.length})</span>
          </h2>
          {activePrompt && (
            <Badge variant="secondary" className="px-3 py-1 text-xs font-medium">
              Filtro IA: {activePrompt}
            </Badge>
          )}
        </div>

        <div className="grid grid-cols-1 gap-5">
          {filteredData.map((item) => (
            <Card key={item.id} className="border-border/80 bg-card hover:border-emerald-500/40 transition-all shadow-md overflow-hidden">
              <CardContent className="p-6 space-y-4">
                
                {/* Header del Caso */}
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-border/60 pb-4">
                  <div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-extrabold font-mono text-emerald-600 dark:text-emerald-400">
                        {item.radicado}
                      </span>
                      <Badge className={
                        item.nivel_riesgo === 'Alto' ? 'bg-red-500/20 text-red-500 border-red-500/40' :
                        item.nivel_riesgo === 'Medio' ? 'bg-amber-500/20 text-amber-500 border-amber-500/40' :
                        'bg-emerald-500/20 text-emerald-500 border-emerald-500/40'
                      }>
                        Riesgo {item.nivel_riesgo}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground font-semibold mt-1">
                      {item.juzgado}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="border-amber-500/40 text-amber-600 dark:text-amber-400 flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" />
                      <span>Vence en {item.termino_dias_restantes} días</span>
                    </Badge>

                    {item.dias_sin_movimiento >= 180 && (
                      <Badge variant="outline" className="border-indigo-500/40 text-indigo-600 dark:text-indigo-400">
                        ❄️ {item.dias_sin_movimiento} días inactivo
                      </Badge>
                    )}
                  </div>
                </div>

                {/* Partes del Proceso */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="bg-muted/40 p-3 rounded-xl border border-border/40">
                    <span className="text-muted-foreground font-bold uppercase tracking-wider block mb-1">Demandante:</span>
                    <span className="font-semibold text-foreground">{item.demandante}</span>
                  </div>
                  <div className="bg-muted/40 p-3 rounded-xl border border-border/40">
                    <span className="text-muted-foreground font-bold uppercase tracking-wider block mb-1">Demandado:</span>
                    <span className="font-semibold text-foreground">{item.demandado}</span>
                  </div>
                </div>

                {/* Resumen e Indicador IA */}
                <div className="space-y-3 pt-2">
                  <div className="p-4 rounded-xl bg-slate-900 text-slate-100 space-y-2 border border-emerald-500/20">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-emerald-400 uppercase tracking-widest flex items-center gap-1.5">
                        <Sparkles className="w-4 h-4" /> Resumen de Actuación (IA)
                      </span>
                    </div>
                    <p className="text-xs md:text-sm leading-relaxed text-slate-200">
                      {item.resumen_ia}
                    </p>
                  </div>

                  <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-900 dark:text-emerald-300 text-xs flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <Zap className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                      <span><strong>Recomendación IA:</strong> {item.recomendacion_ia}</span>
                    </div>
                    <Button size="sm" className="bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs h-8 flex-shrink-0">
                      <span>Ver Detalles</span>
                      <ArrowUpRight className="w-3.5 h-3.5 ml-1" />
                    </Button>
                  </div>
                </div>

              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* COMPARATIVA DE VALOR DE MERCADO (VENTA DE JURICOB vs ICARUS) */}
      <Card className="border-emerald-500/30 bg-gradient-to-br from-slate-900 via-slate-950 to-emerald-950 text-white p-8 rounded-3xl shadow-2xl relative overflow-hidden">
        <div className="relative z-10 space-y-4">
          <Badge className="bg-emerald-500 text-slate-950 font-bold uppercase tracking-widest">
            🚀 Ventaja Competitiva Comercial
          </Badge>
          <h3 className="text-2xl font-bold font-serif-juricob">
            Diferenciador Clave frente a ICARUS y plataformas tradicionales
          </h3>
          <p className="text-slate-300 text-sm md:text-base leading-relaxed max-w-4xl">
            Al incorporar Inteligencia Artificial, Juricob deja de ser una simple herramienta de consulta de la Rama Judicial para convertirse en una plataforma de <strong>Inteligencia Operativa Jurídica</strong>. Esto incrementa exponencialmente el valor del software para la venta a firmas de abogados y entidades financieras.
          </p>
        </div>
      </Card>

    </div>
  );
}
