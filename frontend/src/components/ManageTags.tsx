import { useState, useEffect } from "react";
import { getTags, updateTag, deleteTag, createTag, type Tag } from "@/services/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Loader2, Trash2, Pencil, X, Check, Tag as TagIcon, Activity } from "lucide-react";
import { toast } from "sonner";

export function ManageTags({ mode }: { mode: 'estado' | 'etiqueta' }) {
  const [tags, setTags] = useState<Tag[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [newItemName, setNewItemName] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");

  const fetchTags = async () => {
    setIsLoading(true);
    try {
      const data = await getTags();
      setTags(data);
    } catch (error) {
      toast.error("Error al cargar " + (mode === 'estado' ? 'estados' : 'etiquetas'));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTags();
  }, []);

  const handleCreate = async () => {
    if (!newItemName.trim()) return;
    setIsSubmitting(true);
    try {
      await createTag(newItemName.trim());
      setNewItemName("");
      toast.success(`${mode === 'estado' ? 'Estado creado' : 'Etiqueta creada'} correctamente`);
      fetchTags();
    } catch (error: any) {
      toast.error(error.message || "Error al crear");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUpdate = async (id: number) => {
    if (!editName.trim()) return;
    try {
      await updateTag(id, editName.trim());
      setEditingId(null);
      toast.success("Actualizado correctamente");
      fetchTags();
    } catch (error: any) {
      toast.error(error.message || "Error al actualizar");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm(`¿Seguro que deseas eliminar est${mode === 'estado' ? 'e estado' : 'a etiqueta'}?`)) return;
    try {
      await deleteTag(id);
      toast.success("Eliminado correctamente");
      fetchTags();
    } catch (error: any) {
      toast.error(error.message || "Error al eliminar");
    }
  };

  return (
    <div className="space-y-6">
      {isLoading ? (
        <div className="flex justify-center p-6"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
      ) : (
        <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
          {tags.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">No hay elementos creados aún.</p>
          ) : (
            tags.map(tag => (
              <div key={tag.id} className="flex items-center justify-between p-3 bg-accent/20 border border-border/40 rounded-xl">
                {editingId === tag.id ? (
                  <div className="flex-1 flex items-center gap-2 mr-2">
                    <Input 
                      value={editName} 
                      onChange={(e) => setEditName(e.target.value)} 
                      className="h-8 text-sm"
                      autoFocus
                    />
                    <Button size="icon" variant="ghost" className="h-8 w-8 text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50" onClick={() => handleUpdate(tag.id)}>
                      <Check className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" className="h-8 w-8 text-zinc-400 hover:text-zinc-600" onClick={() => setEditingId(null)}>
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center gap-3">
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: tag.color || '#3b82f6' }} />
                      <span className="text-sm font-semibold">{tag.name}</span>
                    </div>
                    <div className="flex gap-1">
                      <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground hover:text-primary" onClick={() => { setEditingId(tag.id); setEditName(tag.name); }}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground hover:text-red-500 hover:bg-red-50" onClick={() => handleDelete(tag.id)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </>
                )}
              </div>
            ))
          )}
        </div>
      )}

      <div className="pt-4 border-t border-border/40">
        <label className="text-[10px] font-black uppercase text-muted-foreground tracking-widest mb-2 block">
          Crear Nuev{mode === 'estado' ? 'o Estado' : 'a Etiqueta'}
        </label>
        <div className="flex gap-2">
          <Input 
            placeholder={`Ej: ${mode === 'estado' ? 'En Proceso' : 'Urgente'}`}
            value={newItemName}
            onChange={(e) => setNewItemName(e.target.value)}
            className="bg-accent/30 border-border/40 rounded-xl h-10 text-sm font-bold flex-1"
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
          />
          <Button onClick={handleCreate} disabled={isSubmitting || !newItemName.trim()} className="h-10 rounded-xl px-6">
            {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Crear"}
          </Button>
        </div>
      </div>
    </div>
  );
}
