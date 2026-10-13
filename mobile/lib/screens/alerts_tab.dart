import 'package:flutter/material.dart';

import '../api/client.dart';
import '../api/models.dart';
import '../session.dart';
import '../theme.dart';
import '../util/time.dart';
import '../widgets/common.dart';

/// Every notification, newest first. Tapping one marks it read and opens what
/// it is about, through `onOpen`.
class AlertsTab extends StatefulWidget {
  const AlertsTab({super.key, required this.active, required this.onOpen, required this.onUnreadChanged});

  final bool active;

  /// The web path the notification links to, such as `/teacher#makeup-12`.
  final ValueChanged<String> onOpen;
  final ValueChanged<int> onUnreadChanged;

  @override
  State<AlertsTab> createState() => _AlertsTabState();
}

class _AlertsTabState extends State<AlertsTab> {
  List<AppNotification>? _items;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (widget.active) _load();
  }

  @override
  void didUpdateWidget(AlertsTab old) {
    super.didUpdateWidget(old);
    if (widget.active && !old.active) _load();
  }

  Future<void> _load() async {
    try {
      final items = await context.api.notifications();
      if (!mounted) return;
      setState(() {
        _items = items;
        _error = null;
      });
      widget.onUnreadChanged(items.where((n) => n.unread).length);
    } on ApiError catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  Future<void> _open(AppNotification n) async {
    if (n.unread) {
      context.api.markRead(n.id).then((_) => _load()).catchError((Object _) {});
    }
    final link = n.link;
    if (link != null) widget.onOpen(link);
  }

  Future<void> _markAll() async {
    try {
      await context.api.markAllRead();
      await _load();
    } on ApiError catch (e) {
      if (mounted) showMessage(context, e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = context.palette;
    final items = _items;
    final unread = items?.where((n) => n.unread).length ?? 0;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Alerts'),
        actions: [
          if (unread > 0) TextButton(onPressed: _markAll, child: const Text('Mark all read')),
          const SizedBox(width: 6),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: items == null
            ? ListView(
                children: [if (_error != null) LoadError(message: _error!, onRetry: _load) else const Loading()],
              )
            : items.isEmpty
            ? ListView(
                children: const [
                  SizedBox(height: 60),
                  EmptyState(
                    icon: Icons.notifications_none_rounded,
                    title: "You're all caught up",
                    body: 'Reports about your classes and decisions on your reschedules show up here.',
                  ),
                ],
              )
            : ListView.separated(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
                itemCount: items.length,
                separatorBuilder: (_, _) => const SizedBox(height: 10),
                itemBuilder: (context, i) => _NotificationTile(n: items[i], onTap: () => _open(items[i]), palette: p),
              ),
      ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({required this.n, required this.onTap, required this.palette});
  final AppNotification n;
  final VoidCallback onTap;
  final Palette palette;

  (IconData, Color, Color) _look() {
    final p = palette;
    return switch (n.kind) {
      'CLASS_REPORTED' || 'MISSED_CLASS' => (Icons.event_busy_rounded, p.bad, p.badSoft),
      'MAKEUP_SCHEDULED' || 'EXTRA_BOOKED' => (Icons.event_available_rounded, p.ok, p.okSoft),
      'MAKEUP_REMINDER' => (Icons.alarm_rounded, p.warn, p.warnSoft),
      'ONLINE_DECISION' || 'MAKEUP_DECISION' => (Icons.gavel_rounded, p.info, p.infoSoft),
      'ONLINE_REQUEST' || 'MAKEUP_REQUEST' => (Icons.inbox_rounded, p.brand, p.brandSoft),
      _ => (Icons.notifications_rounded, p.brand, p.brandSoft),
    };
  }

  @override
  Widget build(BuildContext context) {
    final p = palette;
    final (icon, fg, bg) = _look();
    return Material(
      color: n.unread ? p.surface : p.surface.withValues(alpha: 0.6),
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
              color: n.unread ? p.brand.withValues(alpha: p.isDark ? 0.25 : 0.35) : p.line,
              width: 1.2,
            ),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(12)),
                child: Icon(icon, color: fg, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            n.title,
                            style: TextStyle(
                              fontSize: 15.5,
                              fontWeight: n.unread ? FontWeight.w800 : FontWeight.w600,
                              color: p.ink,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(relativeTime(n.createdAt), style: TextStyle(fontSize: 12.5, color: p.inkFaint)),
                        if (n.unread) ...[
                          const SizedBox(width: 6),
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Container(
                              width: 8,
                              height: 8,
                              decoration: BoxDecoration(color: p.brandSolid, shape: BoxShape.circle),
                            ),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(n.body, style: TextStyle(fontSize: 14.5, color: p.inkSoft, height: 1.4)),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
