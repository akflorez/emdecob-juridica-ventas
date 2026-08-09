import { useState, useRef } from 'react';
import { Upload, FileSpreadsheet, CheckCircle2, AlertTriangle, Loader2, Download, XCircle, Trash2, Info } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import { importExcel, bulkDeleteExcel, downloadInvalidReport, type ImportExcelResponse } from '@/services/api';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function ImportarPage() {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [importResult, setImportResult] = useState<ImportExcelResponse | null>(null);
  const [deleteResult, setDeleteResult] = useState<{ ok: boolean, deleted_cases: number } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const deleteInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const uploadFile = async (file: File) => {
    const validExtensions = ['.xlsx', '.xls', '.csv'];
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
    
    if (!validExtensions.includes(ext)) {
      toast({
        title: 'Archivo inválido',
        description: 'Solo se permiten archivos .xlsx, .xls o .csv',
        variant: 'destructive',
      });
      return;
    }

    setIsUploading(true);
    setImportResult(null);
    setDeleteResult(null);
    
    try {
      const response = await importExcel(file);
      setImportResult(response);
      
      const totalChanges = response.created + response.updated;
      if (totalChanges > 0) {
        toast({
          title: 'Procesamiento exitoso',
          description: `Se crearon ${response.created} y se actualizaron ${response.updated} caso(s)`,
        });
      } else {
        toast({
          title: 'Sin cambios',
          description: 'No se detectaron radicados nuevos o actualizaciones',
        });
      }
    } catch (error: any) {
      toast({
        title: 'Error al importar',
        description: error?.message || 'Error desconocido',
        variant: 'destructive',
      });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDeleteFile = async (file: File) => {
    if (!confirm("¿Estás seguro de que deseas eliminar masivamente estos radicados? Esta acción no se puede deshacer.")) {
        return;
    }

    setIsUploading(true);
    setImportResult(null);
    setDeleteResult(null);

    try {
      const response = await bulkDeleteExcel(file);
      setDeleteResult(response);
      toast({
        title: 'Eliminación masiva completada',
        description: `Se eliminaron ${response.deleted_cases} procesos correctamente`,
      });
    } catch (error: any) {
      toast({
        title: 'Error al eliminar',
        description: error?.message || 'Error desconocido',
        variant: 'destructive',
      });
    } finally {
      setIsUploading(false);
      if (deleteInputRef.current) deleteInputRef.current.value = '';
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Gestión Masiva</h1>
        <p className="text-muted-foreground mt-2">
          Importa, actualiza o elimina casos de forma masiva mediante archivos Excel
        </p>
      </div>

      <Tabs defaultValue="importar" className="space-y-6">
        <TabsList className="grid w-full grid-cols-2 lg:w-[400px]">
          <TabsTrigger value="importar" className="flex items-center gap-2">
            <Upload className="h-4 w-4" /> Importar / Actualizar
          </TabsTrigger>
          <TabsTrigger value="eliminar" className="flex items-center gap-2">
            <Trash2 className="h-4 w-4" /> Eliminación Masiva
          </TabsTrigger>
        </TabsList>

        <TabsContent value="importar" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-5 w-5 text-primary" />
                Subir Archivo de Importación
              </CardTitle>
              <CardDescription>
                Puedes subir nuevos radicados o actualizar la Cédula y Abogado de radicados existentes.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div
                className={`
                  border-2 border-dashed rounded-lg p-10 text-center transition-colors cursor-pointer
                  ${isDragging ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'}
                  ${isUploading ? 'pointer-events-none opacity-50' : ''}
                `}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={(e) => {
                    e.preventDefault();
                    setIsDragging(false);
                    if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
                }}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xlsx,.xls,.csv"
                  onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])}
                  className="hidden"
                />
                
                {isUploading ? (
                  <div className="space-y-4">
                    <Loader2 className="h-10 w-10 mx-auto text-primary animate-spin" />
                    <p className="text-muted-foreground text-sm">Procesando archivo...</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <FileSpreadsheet className="h-10 w-10 mx-auto text-muted-foreground" />
                    <div>
                      <p className="font-medium text-sm">Arrastra tu Excel aquí o haz clic</p>
                    </div>
                  </div>
                )}
              </div>

              {importResult && (
                <div className="mt-6 grid gap-4 sm:grid-cols-3">
                  <div className="flex items-center gap-3 p-4 rounded-lg bg-green-500/10 border border-green-500/20">
                    <CheckCircle2 className="h-6 w-6 text-green-500" />
                    <div>
                      <p className="text-xl font-bold text-green-500">{importResult.created}</p>
                      <p className="text-xs text-muted-foreground">Nuevos</p>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-3 p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
                    <Info className="h-6 w-6 text-blue-500" />
                    <div>
                      <p className="text-xl font-bold text-blue-500">{importResult.updated}</p>
                      <p className="text-xs text-muted-foreground">Actualizados</p>
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                    <div className="flex items-center gap-3">
                      <AlertTriangle className="h-6 w-6 text-yellow-500" />
                      <div>
                        <p className="text-xl font-bold text-yellow-500">{importResult.skipped}</p>
                        <p className="text-xs text-muted-foreground">Ignorados</p>
                      </div>
                    </div>
                    {importResult.skipped > 0 && (
                      <Button 
                        variant="secondary" 
                        size="sm" 
                        className="h-8 gap-2"
                        onClick={() => {
                          const list = (importResult.skipped_list && importResult.skipped_list.length > 0)
                            ? importResult.skipped_list.map((r: any) => ({
                                radicado: typeof r === 'string' ? r : (r.radicado || "Sin radicado"),
                                motivo: typeof r === 'object' && r.motivo ? r.motivo : "Omitido en la importación / Formato incompleto o vacío"
                              }))
                            : [{ radicado: "Filas omitidas", motivo: `${importResult.skipped} fila(s) vacías o con longitud insuficiente` }];
                          downloadInvalidReport(list);
                        }}
                      >
                        <Download className="h-4 w-4" />
                        Reporte
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Formato Sugerido</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="min-w-full text-xs border border-border rounded-lg">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="px-3 py-1 text-left border-b">Radicado</th>
                      <th className="px-3 py-1 text-left border-b">Cédula</th>
                      <th className="px-3 py-1 text-left border-b">Abogado</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="px-3 py-1 font-mono border-b">11001400...</td>
                      <td className="px-3 py-1 border-b">1032...</td>
                      <td className="px-3 py-1 border-b">Juan Pérez</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="eliminar" className="space-y-6">
          <Card className="border-destructive/30 bg-destructive/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-destructive">
                <Trash2 className="h-5 w-5" />
                Eliminación Masiva
              </CardTitle>
              <CardDescription>
                Sube un Excel con la columna "Radicado". Todos los procesos asociados a esos radicados serán **ELIMINADOS PERMANENTEMENTE**.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div
                className="border-2 border-dashed border-destructive/30 rounded-lg p-10 text-center hover:border-destructive/60 transition-colors cursor-pointer"
                onClick={() => deleteInputRef.current?.click()}
              >
                <input
                  ref={deleteInputRef}
                  type="file"
                  accept=".xlsx,.xls,.csv"
                  onChange={(e) => e.target.files?.[0] && handleDeleteFile(e.target.files[0])}
                  className="hidden"
                />
                <div className="space-y-3">
                  <XCircle className="h-10 w-10 mx-auto text-destructive/60" />
                  <p className="text-sm font-medium text-destructive">Seleccionar archivo para eliminar</p>
                </div>
              </div>

              {deleteResult && (
                <div className="mt-6 p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-center">
                  <p className="text-lg font-bold text-destructive">
                    {deleteResult.deleted_cases} procesos eliminados
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}