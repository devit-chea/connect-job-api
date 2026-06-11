from rest_framework import serializers


class AlphanumericSerializer(serializers.BaseSerializer):

    def to_internal_value(self, data):
        for alphanumeric_field in self.alphanumeric_fields:
            main, sub, main_format = self.get_fields_data(alphanumeric_field)
            main_value = data.get(main)
            is_field_required = getattr(self.fields[main], "required")
            try:
                if not main_value and is_field_required:
                    self.fields[main] = serializers.CharField(required=True)
                elif isinstance(main_value, str):
                    data[sub] = main_value
                    self.fields[main] = serializers.CharField(allow_null=True)
                    data[main] = None
                elif isinstance(main_value, int):
                    self.fields[main] = main_format
            except AssertionError:
                pass
        return super().to_internal_value(data)

    def to_representation(self, instance):
        present_instance = {}
        for alphanumeric_field in self.alphanumeric_fields:
            main, sub, main_format = self.get_fields_data(alphanumeric_field)
            sub_value = getattr(instance, sub)
            main_value = getattr(instance, main)
            if main_value and not sub_value and self.fields[main] != main_format:
                try:
                    self.fields[main] = main_format
                except AssertionError:
                    pass
            present_instance = super().to_representation(instance)
            fields_list = [f.get("main") for f in self.alphanumeric_fields]
            for field in present_instance:
                if field not in fields_list:
                    continue
                for alphanumeric_field in self.alphanumeric_fields:
                    main, sub, _ = self.get_fields_data(alphanumeric_field)
                    if main != field:
                        continue
                    sub_value = present_instance.get(sub)
                    main_value = present_instance.get(main)
                    if not main_value and sub_value:
                        present_instance[main] = sub_value
        return present_instance

    def get_fields_data(self, alphanumeric_field):
        return (
            alphanumeric_field.get("main"),
            alphanumeric_field.get("sub"),
            alphanumeric_field.get("main_format"),
        )
