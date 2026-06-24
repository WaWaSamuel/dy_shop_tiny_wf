import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Plus,
  RefreshCw,
  CheckCircle,
  Image,
  Palette,
  Video,
  LayoutTemplate,
} from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { designApi, type DesignTask } from '../services/api';
import { useLanguage } from '../i18n';

const mockTasks: DesignTask[] = [
  {
    id: '1',
    product_id: 'p1',
    product_name: 'Summer Floral Dress',
    task_type: 'main_image',
    style_template: 'Clean Minimal',
    status: 'completed',
    thumbnail_url: null,
    output_urls: ['/design-output-1.jpg', '/design-output-2.jpg'],
    created_at: '2024-06-15T08:00:00Z',
  },
  {
    id: '2',
    product_id: 'p2',
    product_name: 'Casual Denim Jacket',
    task_type: 'detail_page',
    style_template: 'Lifestyle Scene',
    status: 'generating',
    thumbnail_url: null,
    output_urls: [],
    created_at: '2024-06-15T09:30:00Z',
  },
  {
    id: '3',
    product_id: 'p3',
    product_name: 'Minimalist Leather Bag',
    task_type: 'video_cover',
    style_template: 'Dark Luxury',
    status: 'completed',
    thumbnail_url: null,
    output_urls: ['/design-output-3.jpg'],
    created_at: '2024-06-15T07:00:00Z',
  },
  {
    id: '4',
    product_id: 'p4',
    product_name: 'Sports Running Shoes',
    task_type: 'banner',
    style_template: 'Dynamic Sport',
    status: 'queued',
    thumbnail_url: null,
    output_urls: [],
    created_at: '2024-06-15T10:00:00Z',
  },
  {
    id: '5',
    product_id: 'p5',
    product_name: 'Silk Pajama Set',
    task_type: 'main_image',
    style_template: 'Soft Pastel',
    status: 'approved',
    thumbnail_url: null,
    output_urls: ['/design-output-4.jpg', '/design-output-5.jpg'],
    created_at: '2024-06-14T16:00:00Z',
  },
  {
    id: '6',
    product_id: 'p6',
    product_name: 'Retro Sunglasses',
    task_type: 'main_image',
    style_template: 'Clean Minimal',
    status: 'completed',
    thumbnail_url: null,
    output_urls: ['/design-output-6.jpg'],
    created_at: '2024-06-14T14:00:00Z',
  },
];

const taskTypeIcons: Record<string, typeof Image> = {
  main_image: Image,
  detail_page: LayoutTemplate,
  video_cover: Video,
  banner: Palette,
};

export default function Design() {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const [showNewTask, setShowNewTask] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');

  const { data: taskData } = useQuery({
    queryKey: ['design-tasks', statusFilter],
    queryFn: () =>
      designApi.list({ status: statusFilter || undefined }).then((r) => r.data),
  });

  const regenerateMutation = useMutation({
    mutationFn: (id: string) => designApi.regenerate(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['design-tasks'] }),
  });

  const tasks = taskData?.items ?? mockTasks;

  const filteredTasks = statusFilter
    ? tasks.filter((t) => t.status === statusFilter)
    : tasks;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('design.title')}</h1>
          <p className="text-sm text-gray-500 mt-1">
            {t('design.subtitle')}
          </p>
        </div>
        <button
          className="btn-primary flex items-center gap-2 text-sm"
          onClick={() => setShowNewTask(true)}
        >
          <Plus className="w-4 h-4" />
          {t('design.newTask')}
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <select
          className="input-field w-auto"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">{t('design.allStatus')}</option>
          <option value="queued">{t('status.queued')}</option>
          <option value="generating">{t('status.generating')}</option>
          <option value="completed">{t('status.completed')}</option>
          <option value="approved">{t('status.approved')}</option>
          <option value="rejected">{t('status.rejected')}</option>
        </select>
      </div>

      {/* Task Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredTasks.map((task) => (
          <DesignTaskCard
            key={task.id}
            task={task}
            onRegenerate={() => regenerateMutation.mutate(task.id)}
          />
        ))}
      </div>

      {filteredTasks.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          {t('design.noItems')}
        </div>
      )}

      {/* New Task Modal */}
      {showNewTask && <NewTaskModal onClose={() => setShowNewTask(false)} />}
    </div>
  );
}

function DesignTaskCard({
  task,
  onRegenerate,
}: {
  task: DesignTask;
  onRegenerate: () => void;
}) {
  const { t } = useLanguage();
  const Icon = taskTypeIcons[task.task_type] || Image;

  return (
    <div className="card overflow-hidden hover:shadow-md transition-shadow">
      {/* Thumbnail area */}
      <div className="h-40 bg-gray-100 flex items-center justify-center relative">
        {task.status === 'generating' ? (
          <div className="flex flex-col items-center gap-2">
            <RefreshCw className="w-6 h-6 text-purple-500 animate-spin" />
            <span className="text-xs text-gray-500">{t('design.generating')}</span>
          </div>
        ) : task.output_urls.length > 0 ? (
          <div className="w-full h-full bg-gradient-to-br from-gray-200 to-gray-300 flex items-center justify-center">
            <Icon className="w-10 h-10 text-gray-400" />
          </div>
        ) : (
          <Icon className="w-10 h-10 text-gray-300" />
        )}
        <div className="absolute top-2 right-2">
          <StatusBadge status={task.status} />
        </div>
      </div>

      {/* Info */}
      <div className="p-4 space-y-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-900 truncate">
            {task.product_name}
          </h3>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-gray-500 capitalize">
              {task.task_type.replace('_', ' ')}
            </span>
            <span className="text-xs text-gray-300">|</span>
            <span className="text-xs text-gray-500">{task.style_template}</span>
          </div>
        </div>

        {/* Actions */}
        {(task.status === 'completed' || task.status === 'approved') && (
          <div className="flex items-center gap-2 pt-2 border-t">
            {task.status === 'completed' && (
              <button className="btn-primary flex-1 flex items-center justify-center gap-1.5 text-xs py-1.5">
                <CheckCircle className="w-3.5 h-3.5" />
                {t('design.approve')}
              </button>
            )}
            <button
              className="btn-outline flex-1 flex items-center justify-center gap-1.5 text-xs py-1.5"
              onClick={onRegenerate}
            >
              <RefreshCw className="w-3.5 h-3.5" />
              {t('design.regenerate')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function NewTaskModal({ onClose }: { onClose: () => void }) {
  const [formData, setFormData] = useState({
    productId: '',
    taskType: 'main_image',
    styleTemplate: '',
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="p-6 border-b">
          <h2 className="text-lg font-semibold text-gray-900">New Design Task</h2>
          <p className="text-sm text-gray-500 mt-1">
            Generate AI-powered product images
          </p>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Product
            </label>
            <select
              className="input-field"
              value={formData.productId}
              onChange={(e) => setFormData({ ...formData, productId: e.target.value })}
            >
              <option value="">Select a product</option>
              <option value="p1">Summer Floral Dress</option>
              <option value="p2">Casual Denim Jacket</option>
              <option value="p3">Minimalist Leather Bag</option>
              <option value="p4">Sports Running Shoes</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Task Type
            </label>
            <select
              className="input-field"
              value={formData.taskType}
              onChange={(e) => setFormData({ ...formData, taskType: e.target.value })}
            >
              <option value="main_image">Main Image</option>
              <option value="detail_page">Detail Page</option>
              <option value="video_cover">Video Cover</option>
              <option value="banner">Banner</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Style Template
            </label>
            <select
              className="input-field"
              value={formData.styleTemplate}
              onChange={(e) => setFormData({ ...formData, styleTemplate: e.target.value })}
            >
              <option value="">Select a template</option>
              <option value="clean_minimal">Clean Minimal</option>
              <option value="lifestyle_scene">Lifestyle Scene</option>
              <option value="dark_luxury">Dark Luxury</option>
              <option value="dynamic_sport">Dynamic Sport</option>
              <option value="soft_pastel">Soft Pastel</option>
              <option value="bold_color">Bold Color</option>
            </select>
          </div>
        </div>
        <div className="p-6 border-t flex items-center justify-end gap-3">
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={onClose}>
            Create Task
          </button>
        </div>
      </div>
    </div>
  );
}
