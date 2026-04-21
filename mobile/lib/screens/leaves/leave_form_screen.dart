import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../config/theme.dart';
import '../../providers/leave_provider.dart';

class LeaveFormScreen extends StatefulWidget {
  const LeaveFormScreen({super.key});

  @override
  State<LeaveFormScreen> createState() => _LeaveFormScreenState();
}

class _LeaveFormScreenState extends State<LeaveFormScreen> {
  final _formKey = GlobalKey<FormState>();
  int? _selectedLeaveType;
  DateTime? _startDate;
  DateTime? _endDate;
  final _reasonCtrl = TextEditingController();
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<LeaveProvider>().loadLeaves();
    });
  }

  @override
  void dispose() {
    _reasonCtrl.dispose();
    super.dispose();
  }

  int get _workingDays {
    if (_startDate == null || _endDate == null) return 0;
    int days = 0;
    var d = _startDate!;
    while (!d.isAfter(_endDate!)) {
      if (d.weekday != DateTime.saturday && d.weekday != DateTime.sunday) days++;
      d = d.add(const Duration(days: 1));
    }
    return days;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_startDate == null || _endDate == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select start and end dates')),
      );
      return;
    }

    setState(() => _submitting = true);
    final provider = context.read<LeaveProvider>();
    final ok = await provider.createLeave(
      leaveTypeId: _selectedLeaveType!,
      startDate: _startDate!.toIso8601String().split('T')[0],
      endDate: _endDate!.toIso8601String().split('T')[0],
      reason: _reasonCtrl.text.trim(),
    );

    if (!mounted) return;
    setState(() => _submitting = false);

    if (ok) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('Leave request submitted'),
          backgroundColor: AppTheme.semantics(context).success,
        ),
      );
      Navigator.pop(context);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(provider.error ?? 'Failed to submit'),
          backgroundColor: AppTheme.semantics(context).danger,
        ),
      );
    }
  }

  Future<void> _pickDate(bool isStart) async {
    final initial = (isStart ? _startDate : _endDate) ?? DateTime.now();
    final first = isStart ? DateTime.now() : (_startDate ?? DateTime.now());
    final picked = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: first,
      lastDate: DateTime.now().add(const Duration(days: 365)),
      builder: (ctx, child) => Theme(
        data: Theme.of(ctx),
        child: child!,
      ),
    );
    if (picked != null) {
      setState(() {
        if (isStart) {
          _startDate = picked;
          if (_endDate != null && _endDate!.isBefore(picked)) _endDate = picked;
        } else {
          _endDate = picked;
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<LeaveProvider>();
    final isDark = Theme.of(context).brightness == Brightness.dark;

    final selectedBalance = _selectedLeaveType != null
        ? provider.balances.where((b) => b.leaveTypeId == _selectedLeaveType).firstOrNull
        : null;

    return Scaffold(
      backgroundColor: isDark ? MColors.darkBg : MColors.bg,
      body: SafeArea(
        child: Column(
          children: [
            // Top bar
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
              child: Row(
                children: [
                  GestureDetector(
                    onTap: () => Navigator.pop(context),
                    child: Icon(Icons.close_rounded, size: 22,
                        color: isDark ? MColors.darkText : MColors.text),
                  ),
                  const Spacer(),
                  Text('New Leave Request', style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w700,
                    color: isDark ? MColors.darkText : MColors.text,
                  )),
                  const Spacer(),
                  const SizedBox(width: 22),
                ],
              ),
            ),

            Expanded(
              child: Form(
                key: _formKey,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                  children: [
                    // Leave type dropdown
                    _Label('Leave type'),
                    const SizedBox(height: 8),
                    Container(
                      decoration: BoxDecoration(
                        color: isDark ? MColors.darkSurfaceAlt : MColors.surfaceAlt,
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(
                          color: isDark ? MColors.darkBorder : MColors.border, width: 1,
                        ),
                      ),
                      child: DropdownButtonFormField<int>(
                        initialValue: _selectedLeaveType,
                        decoration: const InputDecoration(
                          border: InputBorder.none,
                          contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                        ),
                        hint: Text('Select leave type',
                            style: TextStyle(color: isDark ? MColors.darkTextFaint : MColors.textFaint)),
                        items: provider.leaveTypes.map((t) {
                          final bal = provider.balances
                              .where((b) => b.leaveTypeId == t.id).firstOrNull;
                          return DropdownMenuItem(
                            value: t.id,
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(t.name),
                                if (bal != null)
                                  Text('${bal.remaining.toStringAsFixed(0)} days left',
                                      style: TextStyle(fontSize: 12,
                                          color: isDark ? MColors.darkTextSub : MColors.textSub)),
                              ],
                            ),
                          );
                        }).toList(),
                        onChanged: (v) => setState(() => _selectedLeaveType = v),
                        validator: (v) => v == null ? 'Select a leave type' : null,
                        dropdownColor: isDark ? MColors.darkSurfaceAlt : MColors.surface,
                      ),
                    ),

                    // Balance preview
                    if (selectedBalance != null) ...[
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                        decoration: BoxDecoration(
                          color: isDark ? MColors.darkPrimarySoft : MColors.primarySoft,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Row(
                          children: [
                            Icon(Icons.info_outline_rounded, size: 14,
                                color: isDark ? MColors.darkPrimary : MColors.primary),
                            const SizedBox(width: 8),
                            Text(
                              '${selectedBalance.remaining.toStringAsFixed(0)} days remaining of ${selectedBalance.daysAllowed} allowed',
                              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500,
                                  color: isDark ? MColors.darkPrimary : MColors.primary),
                            ),
                          ],
                        ),
                      ),
                    ],

                    const SizedBox(height: 20),

                    // Date pickers row
                    Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              _Label('Start date'),
                              const SizedBox(height: 8),
                              _DateField(
                                value: _startDate,
                                hint: 'Select date',
                                onTap: () => _pickDate(true),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              _Label('End date'),
                              const SizedBox(height: 8),
                              _DateField(
                                value: _endDate,
                                hint: 'Select date',
                                onTap: () => _pickDate(false),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),

                    // Working days calculation
                    if (_startDate != null && _endDate != null) ...[
                      const SizedBox(height: 10),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                        decoration: BoxDecoration(
                          color: isDark ? MColors.darkSuccessSoft : MColors.successSoft,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Row(
                          children: [
                            Icon(Icons.check_circle_outline_rounded, size: 14,
                                color: isDark ? MColors.darkSuccess : MColors.success),
                            const SizedBox(width: 8),
                            Text(
                              '$_workingDays working ${_workingDays == 1 ? 'day' : 'days'} selected',
                              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600,
                                  color: isDark ? MColors.darkSuccess : MColors.success),
                            ),
                          ],
                        ),
                      ),
                    ],

                    const SizedBox(height: 20),

                    // Reason
                    _Label('Reason (optional)'),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: _reasonCtrl,
                      maxLines: 4,
                      maxLength: 500,
                      decoration: InputDecoration(
                        hintText: 'Add a note for your manager...',
                        hintStyle: TextStyle(
                            color: isDark ? MColors.darkTextFaint : MColors.textFaint,
                            fontSize: 14),
                        alignLabelWithHint: true,
                      ),
                    ),

                    const SizedBox(height: 24),

                    SizedBox(
                      height: 54,
                      child: ElevatedButton(
                        onPressed: _submitting ? null : _submit,
                        child: _submitting
                            ? const SizedBox(width: 20, height: 20,
                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                            : const Text('Submit request',
                                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Label extends StatelessWidget {
  final String text;
  const _Label(this.text);
  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Text(text, style: TextStyle(
      fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 0.1,
      color: isDark ? MColors.darkTextMid : MColors.textMid,
    ));
  }
}

class _DateField extends StatelessWidget {
  final DateTime? value;
  final String hint;
  final VoidCallback onTap;
  const _DateField({this.value, required this.hint, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        height: 52,
        padding: const EdgeInsets.symmetric(horizontal: 14),
        decoration: BoxDecoration(
          color: isDark ? MColors.darkSurfaceAlt : MColors.surfaceAlt,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: isDark ? MColors.darkBorder : MColors.border),
        ),
        child: Row(
          children: [
            Icon(Icons.calendar_today_outlined, size: 16,
                color: isDark ? MColors.darkTextSub : MColors.textSub),
            const SizedBox(width: 10),
            Text(
              value != null
                  ? '${value!.year}-${value!.month.toString().padLeft(2, '0')}-${value!.day.toString().padLeft(2, '0')}'
                  : hint,
              style: TextStyle(
                fontSize: 14, fontWeight: FontWeight.w500,
                color: value != null
                    ? (isDark ? MColors.darkText : MColors.text)
                    : (isDark ? MColors.darkTextFaint : MColors.textFaint),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
