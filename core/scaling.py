class ScalingManager:
    def __init__(self, min_scale=0.3, max_scale=1.6):
        self.scale = 1.0
        self.min_scale = min_scale
        self.max_scale = max_scale

    def increase(self):
        self.scale = min(self.scale + 0.1, self.max_scale)
        return self.scale

    def decrease(self):
        self.scale = max(self.scale - 0.1, self.min_scale)
        return self.scale
 
