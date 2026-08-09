import { useState, useEffect, useCallback } from "react";
import {
  AlertTriangle,
  Search,
  Trash2,
  RefreshCw,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Download,
  CheckCircle2,
  XCircle,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useToast } from "@/hooks/use-toast";

import {
  getInvalidRadicados,
  deleteInvalidRadicado,
  deleteAllInvalidRadicados,
  retryInvalidRadicado,
  downloadInvalidRadicadosExcel,
  type InvalidRadicado,
} from "@/services/api";

export default function NoEncontradosPage() {
  const [rows, setRows] = useState<InvalidRadicado[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [retryingId, setRetryingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const [searchInput, setSearchInput] = useState("");
  const [appliedSearch, setAppliedSearch] = useState<string | undefined>(undefined);

  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;

  const { toast } = useToast();

  const formatDate = (dateString?: string | null) => {
    if (!dateString) return "—";
    const d = new Date(dateString);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleDateString("es-CO", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await getInvalidRadicados({
        search: appliedSearch,
        page,
        page_size: pageSize,
      });

      setRows(response.items || []);
      setTotal(response.total || 0);

      const tp = Math.max(1, Math.ceil((response.total || 0) / pageSize));
      setTotalPages(tp);

      if (page > tp) setPage(tp);
    } catch (error: any) {
      toast({
        title: "Error al cargar datos",
        description: error?.message || "Error desconocido",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  }, [appliedSearch, page, toast]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleFilter = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setAppliedSearch(searchInput.trim() || undefined);
  };

  const handleRetry = async (item: InvalidRadicado) => {
    setRetryingId(item.id);
    try {
      const result = await retryInvalidRadicado(item.id);
      
      if (result.found) {
        const isAlternative = result.source && result.source !== "rama_judicial";
        toast({
          title: isAlternative ? "✅ Encontrado en fuente alternativa" : "✅ ¡Radicado encontrado!",
          description: result.message || `El radicado ${item.radicado} fue agregado a los casos`,
        });
      } else {
        toast({
          title: "No encontrado",
          description: "El radicado no aparece en Rama Judicial ni en fuentes alternativas",
          variant: "destructive",
        });
      }
      
      fetchData();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error?.message || "Error al reintentar",
        variant: "destructive",
      });
    } finally {
      setRetryingId(null);
    }
  };

  const handleDelete = async (item: InvalidRadicado) => {
    setDeletingId(item.id);
    try {
      await deleteInvalidRadicado(item.id);
      toast({
        title: "Eliminado",
        description: `El radicado ${item.radicado} fue eliminado de la lista`,
      });
      fetchData();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error?.message || "Error al eliminar",
        variant: "destructive",
      });
    } finally {
      setDeletingId(null);
    }
  };

  const handleDeleteAll = async () => {
    if (!confirm(`¿Eliminar TODOS los ${total} radicados no encontrados?\n\nEsta acción no se puede deshacer.`)) return;
    try {
      const res = await deleteAllInvalidRadicados();
      toast({
        title: "Eliminados",
        description: res.message || "Se eliminaron todos los radicados no encontrados",
      });
      fetchData();
    } catch (error: any) {
      const msg = error?.detail ? (typeof error.detail === 'string' ? error.detail : JSON.stringify(error.detail)) : (error?.message || "Error al eliminar");
      toast({
        title: "Error",
        description: msg,
        variant: "destructive",
      });
    }
  };

  const handleDownload = () => {
    downloadInvalidRadicadosExcel();
    toast({
      title: "Descargando...",
      description: "El archivo Excel se descargará en unos segundos",
    });
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Radicados No Encontrados</h1>
          <p className="text-muted-foreground mt-2">
            Radicados que no se encontraron en la página de la Rama Judicial
          </p>
        </div>

        {total > 0 && (
          <div className="flex items-center gap-2">
            <Button onClick={handleDownload} variant="outline">
              <Download className="h-4 w-4 mr-2" />
              Descargar Excel
            </Button>
            <Button onClick={handleDeleteAll} variant="destructive">
              <Trash2 className="h-4 w-4 mr-2" />
              Eliminar todos
            </Button>
          </div>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-5 w-5 text-primary" />
            Buscar
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleFilter} className="flex gap-3">
            <Input
              placeholder="Buscar por radicado..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="flex-1"
            />
            <Button type="submit" disabled={isLoading}>
              <Search className="mr-2 h-4 w-4" />
              Buscar
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-yellow-500" />
                Resultados
              </CardTitle>
              <span className="text-sm text-muted-foreground">
                {total} radicado(s) no encontrado(s)
              </span>
            </div>
          </div>
          <CardDescription>
            Puedes reintentar la búsqueda o eliminar los radicados que ya no necesites
          </CardDescription>
        </CardHeader>

        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : rows.length === 0 ? (
            <div className="text-center py-12">
              <CheckCircle2 className="h-12 w-12 mx-auto text-green-500 mb-4" />
              <p className="text-muted-foreground">No hay radicados pendientes</p>
              <p className="text-sm text-muted-foreground mt-1">
                Todos los radicados importados fueron encontrados en Rama Judicial
              </p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Radicado</TableHead>
                      <TableHead>Motivo</TableHead>
                      <TableHead className="text-center">Intentos</TableHead>
                      <TableHead>Último intento</TableHead>
                      <TableHead className="text-right">Acciones</TableHead>
                    </TableRow>
                  </TableHeader>

                  <TableBody>
                    {rows.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="font-mono text-sm">
                          {item.radicado}
                        </TableCell>

                        <TableCell className="text-sm text-muted-foreground">
                          {item.motivo}
                        </TableCell>

                        <TableCell className="text-center">
                          <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-yellow-500/10 text-yellow-600 font-medium">
                            {item.intentos}
                          </span>
                        </TableCell>

                        <TableCell className="text-sm text-muted-foreground">
                          {formatDate(item.updated_at)}
                        </TableCell>

                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleRetry(item)}
                              disabled={retryingId === item.id}
                            >
                              {retryingId === item.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <RefreshCw className="h-4 w-4" />
                              )}
                              <span className="ml-1 hidden sm:inline">Reintentar</span>
                            </Button>

                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-destructive hover:text-destructive"
                                  disabled={deletingId === item.id}
                                >
                                  {deletingId === item.id ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                  ) : (
                                    <Trash2 className="h-4 w-4" />
                                  )}
                                </Button>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>¿Eliminar radicado?</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    Se eliminará el radicado <strong>{item.radicado}</strong> de la lista.
                                    Esta acción no se puede deshacer.
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Cancelar</AlertDialogCancel>
                                  <AlertDialogAction
                                    onClick={() => handleDelete(item)}
                                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                  >
                                    Eliminar
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
                  <p className="text-sm text-muted-foreground">
                    Página {page} de {totalPages}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Anterior
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                    >
                      Siguiente
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}